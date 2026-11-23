"""Resume text extraction (Phase 4.4 / Prompt 5).

Extracts plain text from an uploaded resume file. Supports PDF via ``pypdf``
and DOCX via ``python-docx`` only. No OCR, no scanned-image support.

Validates:
- Real file signatures (%PDF-, PK) independently of file extensions.
- Encrypted or password-protected PDF detection.
- PDF page limit constraints.
- DOCX archive integrity: zip bomb uncompressed size limit, archive entry count limit,
  directory traversal checks, and required WordProcessingML structure ([Content_Types].xml,
  word/document.xml).
- Text extraction from both paragraphs and table cells.
- Controlled, structured error codes without leaking server filesystem paths or secrets.
"""

from __future__ import annotations

import io
import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.errors import (
    UPLOAD_ERROR_CORRUPT,
    UPLOAD_ERROR_ENCRYPTED,
    UPLOAD_ERROR_INVALID_ARCHIVE,
    UPLOAD_ERROR_NO_TEXT,
    UPLOAD_ERROR_PAGE_LIMIT_EXCEEDED,
    UPLOAD_ERROR_TOO_LARGE,
    UPLOAD_ERROR_UNSUPPORTED_TYPE,
    UploadValidationError,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = frozenset({"pdf", "docx"})

# Content types (lower-cased) accepted alongside the matching extension.
PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

EXTENSION_TO_CONTENT_TYPE = {
    "pdf": PDF_CONTENT_TYPE,
    "docx": DOCX_CONTENT_TYPE,
}

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK"
_OCR_SEMAPHORE = threading.BoundedSemaphore(settings.ocr_max_concurrent_jobs)


@dataclass(frozen=True)
class ExtractedDocumentText:
    text: str
    source: str = "text_layer"
    confidence: float | None = None
    needs_manual_review: bool = False


class TextExtractor(ABC):
    """Extract plain text from one supported file format."""

    extension: str

    @abstractmethod
    def extract(self, data: bytes) -> str:
        """Return the extracted text, raising UploadValidationError if unextractable."""


class PdfTextExtractor(TextExtractor):
    extension = "pdf"

    def extract(self, data: bytes, *, max_pages: int | None = None) -> str:
        if not data:
            raise UploadValidationError("Uploaded PDF file is empty.", code=UPLOAD_ERROR_NO_TEXT)

        if not data.startswith(PDF_MAGIC):
            raise UploadValidationError(
                "File content does not match PDF signature.",
                code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
            )

        from pypdf import PdfReader
        from pypdf.errors import PyPdfError

        effective_max_pages = max_pages if max_pages is not None else settings.max_pdf_pages

        try:
            reader = PdfReader(io.BytesIO(data))
        except (PyPdfError, ValueError, OSError, Exception) as exc:
            logger.warning("PDF reader initialization failed: %s", type(exc).__name__)
            raise UploadValidationError(
                "Uploaded PDF could not be read or is corrupt.",
                code=UPLOAD_ERROR_CORRUPT,
            ) from exc

        if reader.is_encrypted:
            raise UploadValidationError(
                "Encrypted or password-protected PDF files are not supported.",
                code=UPLOAD_ERROR_ENCRYPTED,
            )

        try:
            num_pages = len(reader.pages)
        except Exception as exc:
            raise UploadValidationError(
                "Failed to determine PDF page count.",
                code=UPLOAD_ERROR_CORRUPT,
            ) from exc

        if num_pages > effective_max_pages:
            raise UploadValidationError(
                f"PDF page count ({num_pages}) exceeds the maximum allowed limit of "
                f"{effective_max_pages} pages.",
                code=UPLOAD_ERROR_PAGE_LIMIT_EXCEEDED,
            )

        pages: list[str] = []
        for idx, page in enumerate(reader.pages):
            try:
                t = page.extract_text() or ""
                pages.append(t)
            except Exception as exc:
                logger.warning(
                    "Error extracting text from PDF page %d: %s", idx, type(exc).__name__
                )
                raise UploadValidationError(
                    f"Failed to extract text from page {idx + 1} of PDF.",
                    code=UPLOAD_ERROR_CORRUPT,
                ) from exc

        text = "\n".join(pages).strip()
        if not text:
            raise UploadValidationError(
                "No extractable text was found in the uploaded file.",
                code=UPLOAD_ERROR_NO_TEXT,
            )
        return text


def _run_bounded_process(
    command: list[str], *, input_bytes: bytes | None, timeout_seconds: float
) -> subprocess.CompletedProcess[bytes]:
    """Run a local document tool with a hard timeout and no shell interpolation."""
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(input=input_bytes, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise UploadValidationError(
            "OCR exceeded its processing time limit.", code="OCR_TIMEOUT"
        ) from None
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _ocr_pdf(data: bytes, *, max_pages: int) -> ExtractedDocumentText:
    """OCR a scanned PDF locally; only raster pages may touch a private temp directory."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UploadValidationError(
                "Encrypted or password-protected PDF files are not supported.",
                code=UPLOAD_ERROR_ENCRYPTED,
            )
        page_count = len(reader.pages)
    except UploadValidationError:
        raise
    except Exception as exc:
        logger.warning("OCR PDF validation failed: %s", type(exc).__name__)
        raise UploadValidationError(
            "Uploaded PDF could not be read or is corrupt.", code=UPLOAD_ERROR_CORRUPT
        ) from exc
    if page_count > max_pages:
        raise UploadValidationError(
            f"PDF page count ({page_count}) exceeds the maximum allowed limit of "
            f"{max_pages} pages.",
            code=UPLOAD_ERROR_PAGE_LIMIT_EXCEEDED,
        )

    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    if not pdftoppm or not tesseract:
        raise UploadValidationError(
            "Local OCR is unavailable because its required tools are not installed.",
            code="OCR_UNAVAILABLE",
        )

    deadline = time.monotonic() + settings.ocr_file_timeout_seconds
    pieces: list[str] = []
    confidences: list[tuple[float, int]] = []
    acquired = _OCR_SEMAPHORE.acquire(timeout=settings.ocr_file_timeout_seconds)
    if not acquired:
        raise UploadValidationError(
            "OCR is at its concurrent-job limit. Try again later.", code="OCR_BUSY"
        )
    try:
        with tempfile.TemporaryDirectory(prefix="hera-ocr-") as temp_name:
            temp_dir = Path(temp_name)
            if os.name != "nt":
                os.chmod(temp_dir, 0o700)
            for page_number in range(1, page_count + 1):
                page_deadline = min(deadline, time.monotonic() + settings.ocr_page_timeout_seconds)
                remaining = page_deadline - time.monotonic()
                if remaining <= 0:
                    raise UploadValidationError(
                        "OCR exceeded its file processing time limit.", code="OCR_TIMEOUT"
                    )
                page_root = temp_dir / f"page-{page_number}"
                render = _run_bounded_process(
                    [
                        pdftoppm,
                        "-f",
                        str(page_number),
                        "-l",
                        str(page_number),
                        "-singlefile",
                        "-gray",
                        "-scale-to",
                        str(settings.ocr_max_page_dimension),
                        "-png",
                        "-",
                        str(page_root),
                    ],
                    input_bytes=data,
                    timeout_seconds=remaining,
                )
                if render.returncode != 0:
                    raise UploadValidationError(
                        "The PDF page could not be rasterized for OCR.",
                        code=UPLOAD_ERROR_CORRUPT,
                    )
                image_path = page_root.with_suffix(".png")
                if not image_path.is_file():
                    raise UploadValidationError(
                        "The PDF page produced no image for OCR.", code=UPLOAD_ERROR_CORRUPT
                    )
                remaining = page_deadline - time.monotonic()
                if remaining <= 0:
                    raise UploadValidationError(
                        "OCR exceeded its file processing time limit.", code="OCR_TIMEOUT"
                    )
                recognized = _run_bounded_process(
                    [tesseract, "stdin", "stdout", "-l", "eng+ara", "tsv", "--psm", "6"],
                    input_bytes=image_path.read_bytes(),
                    timeout_seconds=remaining,
                )
                if recognized.returncode != 0:
                    raise UploadValidationError(
                        "Tesseract could not recognize the PDF page.", code="OCR_FAILED"
                    )
                lines = recognized.stdout.decode("utf-8", errors="replace").splitlines()
                words: list[str] = []
                for line in lines[1:]:
                    columns = line.split("\t", 11)
                    if len(columns) != 12 or not columns[11].strip():
                        continue
                    try:
                        confidence = float(columns[10])
                    except ValueError:
                        continue
                    if math.isfinite(confidence) and confidence >= 0:
                        word = columns[11].strip()
                        words.append(word)
                        confidences.append((confidence, max(1, len(word))))
                if words:
                    pieces.append(" ".join(words))
    except UploadValidationError:
        raise
    except OSError as exc:
        logger.warning("OCR tool execution failed: %s", type(exc).__name__)
        raise UploadValidationError("Local OCR failed to run.", code="OCR_FAILED") from exc
    finally:
        _OCR_SEMAPHORE.release()

    text = "\n".join(pieces).strip()
    if not text or not confidences:
        raise UploadValidationError(
            "OCR found no readable text. The document needs manual review.",
            code=UPLOAD_ERROR_NO_TEXT,
        )
    confidence = (
        sum(value * weight for value, weight in confidences)
        / sum(weight for _, weight in confidences)
        / 100
    )
    return ExtractedDocumentText(
        text=text,
        source="ocr",
        confidence=confidence,
        needs_manual_review=confidence < settings.ocr_confidence_threshold,
    )


def extract_document_text(
    data: bytes,
    *,
    filename: str | None,
    max_pdf_pages: int | None = None,
    max_docx_uncompressed_bytes: int | None = None,
    max_docx_entries: int | None = None,
) -> ExtractedDocumentText:
    """Extract resume text and use local OCR only when called by the worker."""
    try:
        return ExtractedDocumentText(
            text=extract_text(
                data,
                filename=filename,
                max_pdf_pages=max_pdf_pages,
                max_docx_uncompressed_bytes=max_docx_uncompressed_bytes,
                max_docx_entries=max_docx_entries,
            )
        )
    except UploadValidationError as exc:
        extension = Path(filename or "").suffix.lower().lstrip(".")
        if extension != "pdf" or exc.code != UPLOAD_ERROR_NO_TEXT:
            raise
    effective_max_pages = max_pdf_pages if max_pdf_pages is not None else settings.max_pdf_pages
    return _ocr_pdf(data, max_pages=effective_max_pages)


class DocxTextExtractor(TextExtractor):
    extension = "docx"

    def extract(
        self,
        data: bytes,
        *,
        max_uncompressed_bytes: int | None = None,
        max_entries: int | None = None,
    ) -> str:
        if not data:
            raise UploadValidationError("Uploaded DOCX file is empty.", code=UPLOAD_ERROR_NO_TEXT)

        if not data.startswith(ZIP_MAGIC):
            raise UploadValidationError(
                "File content does not match DOCX/ZIP signature.",
                code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
            )

        from zipfile import BadZipFile, ZipFile

        from docx import Document

        effective_max_uncompressed = (
            max_uncompressed_bytes
            if max_uncompressed_bytes is not None
            else settings.max_docx_uncompressed_bytes
        )
        effective_max_entries = (
            max_entries if max_entries is not None else settings.max_docx_entries
        )

        # Inspect ZIP metadata in memory without filesystem extraction
        try:
            with ZipFile(io.BytesIO(data)) as zf:
                namelist = zf.namelist()
                if len(namelist) > effective_max_entries:
                    raise UploadValidationError(
                        f"DOCX archive entry count ({len(namelist)}) exceeds limit of "
                        f"{effective_max_entries}.",
                        code=UPLOAD_ERROR_INVALID_ARCHIVE,
                    )

                total_uncompressed = 0
                for info in zf.infolist():
                    if (
                        info.filename.startswith("/")
                        or info.filename.startswith("\\")
                        or ".." in info.filename
                    ):
                        raise UploadValidationError(
                            "DOCX archive contains unsafe file paths.",
                            code=UPLOAD_ERROR_INVALID_ARCHIVE,
                        )

                    total_uncompressed += info.file_size
                    if total_uncompressed > effective_max_uncompressed:
                        raise UploadValidationError(
                            "DOCX declared uncompressed size exceeds maximum limit of "
                            f"{effective_max_uncompressed} bytes.",
                            code=UPLOAD_ERROR_TOO_LARGE,
                        )

                # Validate required WordProcessingML structural entries
                if "[Content_Types].xml" not in namelist or "word/document.xml" not in namelist:
                    raise UploadValidationError(
                        "Invalid DOCX archive: missing required WordProcessingML parts.",
                        code=UPLOAD_ERROR_INVALID_ARCHIVE,
                    )
        except BadZipFile as exc:
            raise UploadValidationError(
                "Uploaded DOCX archive is corrupt or invalid.",
                code=UPLOAD_ERROR_CORRUPT,
            ) from exc

        try:
            document = Document(io.BytesIO(data))
            paragraphs = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]

            table_lines: list[str] = []
            for table in document.tables:
                for row in table.rows:
                    cell_texts = [
                        cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()
                    ]
                    if cell_texts:
                        table_lines.append(" | ".join(cell_texts))

            all_lines = paragraphs + table_lines
            text = "\n".join(all_lines).strip()
        except (BadZipFile, OSError, ValueError, Exception) as exc:
            logger.warning("DOCX document parsing failed: %s", type(exc).__name__)
            raise UploadValidationError(
                "Uploaded DOCX could not be read or is corrupt.",
                code=UPLOAD_ERROR_CORRUPT,
            ) from exc

        if not text:
            raise UploadValidationError(
                "No extractable text was found in the uploaded file.",
                code=UPLOAD_ERROR_NO_TEXT,
            )
        return text


_EXTRACTORS: dict[str, TextExtractor] = {
    PdfTextExtractor.extension: PdfTextExtractor(),
    DocxTextExtractor.extension: DocxTextExtractor(),
}


def extract_text(
    data: bytes,
    *,
    filename: str | None,
    max_pdf_pages: int | None = None,
    max_docx_uncompressed_bytes: int | None = None,
    max_docx_entries: int | None = None,
) -> str:
    """Extract text from resume bytes, validating type and extractability."""
    if not filename or not filename.strip():
        raise UploadValidationError(
            "An uploaded file must have a filename.",
            code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
        )
    extension = Path(filename).suffix.lower().lstrip(".")
    extractor = _EXTRACTORS.get(extension)
    if extractor is None:
        raise UploadValidationError(
            f"Unsupported file type: {extension or 'unknown'!r}. Only .pdf and .docx are allowed.",
            code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
        )

    if isinstance(extractor, PdfTextExtractor):
        return extractor.extract(data, max_pages=max_pdf_pages)
    elif isinstance(extractor, DocxTextExtractor):
        return extractor.extract(
            data,
            max_uncompressed_bytes=max_docx_uncompressed_bytes,
            max_entries=max_docx_entries,
        )
    return extractor.extract(data)


def extension_for_filename(filename: str) -> str:
    """Return the lowercase extension (without dot), or raise if unsupported."""
    if not filename or not filename.strip():
        raise UploadValidationError(
            "An uploaded file must have a filename.",
            code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
        )
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in SUPPORTED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file type: {extension or 'unknown'!r}. Only .pdf and .docx are allowed.",
            code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
        )
    return extension
