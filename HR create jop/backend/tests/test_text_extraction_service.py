"""Tests for the Phase 4.4 text extraction service."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.errors import UploadValidationError, ValidationError
from app.services.text_extraction_service import (
    DOCX_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    extension_for_filename,
    extract_document_text,
    extract_text,
)
from tests.resume_upload_fixtures import (
    DOCX_TEXT,
    PDF_TEXT,
    make_docx_bytes,
    make_image_pdf,
    make_pdf_bytes,
    scanned_image,
)


def test_extract_pdf_text() -> None:
    text = extract_text(make_pdf_bytes(), filename="resume.pdf")
    assert PDF_TEXT in text


def test_extract_docx_text() -> None:
    text = extract_text(make_docx_bytes(), filename="resume.docx")
    assert DOCX_TEXT in text


def test_wrong_content_type_mismatch_is_not_enforced_here() -> None:
    # extract_text works on bytes + filename only; content-type matching is
    # validated by the service layer. A .pdf with a .docx filename still raises.
    pdf = make_pdf_bytes()
    with pytest.raises(ValidationError):
        extract_text(pdf, filename="resume.docx")


@pytest.mark.parametrize(
    "filename",
    ["resume.txt", "resume.png", "resume", "resume.exe", ""],
)
def test_unsupported_extension_raises(filename: str) -> None:
    if filename:
        with pytest.raises(ValidationError):
            extract_text(b"some bytes", filename=filename)
    else:
        with pytest.raises(ValidationError):
            extract_text(b"some bytes", filename=filename)


def test_no_filename_raises() -> None:
    with pytest.raises(ValidationError):
        extract_text(b"bytes", filename="")


def test_empty_text_raises() -> None:
    # A valid PDF with no extractable text yields no text -> ValidationError.
    with pytest.raises(ValidationError):
        extract_text(b"%PDF-1.4\nnot a real pdf", filename="resume.pdf")


def test_extension_for_filename_ok() -> None:
    assert extension_for_filename("resume.PDF") == "pdf"
    assert extension_for_filename("resume.docx") == "docx"


def test_extension_for_filename_unsupported() -> None:
    with pytest.raises(ValidationError):
        extension_for_filename("resume.txt")


def test_content_type_constants() -> None:
    assert PDF_CONTENT_TYPE == "application/pdf"
    assert DOCX_CONTENT_TYPE == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [("scan_en.jpg", "Ada"), ("scan_ar.jpg", "بيانات")],
)
def test_scanned_pdf_uses_local_ocr_with_confidence(fixture: str, expected: str) -> None:
    image = scanned_image(fixture)
    result = extract_document_text(make_image_pdf([image]), filename="synthetic.pdf")

    assert result.source == "ocr"
    assert result.confidence is not None and 0 <= result.confidence <= 1
    assert expected in result.text


def test_scanned_pdf_skips_blank_page_and_keeps_ocr_text() -> None:
    image = scanned_image("scan_en.jpg")
    result = extract_document_text(make_image_pdf([image, None]), filename="synthetic.pdf")

    assert "Ada" in result.text
    assert result.source == "ocr"


def test_scanned_pdf_page_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import text_extraction_service as service

    monkeypatch.setattr(service.settings, "max_pdf_pages", 1)
    image = scanned_image("scan_en.jpg")
    with pytest.raises(UploadValidationError) as error:
        extract_document_text(make_image_pdf([image, None]), filename="synthetic.pdf")
    assert error.value.code == "PAGE_LIMIT_EXCEEDED"


def test_corrupt_pdf_is_not_misreported_as_empty_text() -> None:
    with pytest.raises(UploadValidationError) as error:
        extract_document_text(b"%PDF-1.4\nnot a valid document", filename="corrupt.pdf")
    assert error.value.code == "CORRUPT"


def test_ocr_timeout_kills_process(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    from app.services import text_extraction_service as service

    class TimedOutProcess:
        returncode = None
        killed = False

        def __init__(self, *_args, **_kwargs):
            self.calls = 0

        def communicate(self, *, input=None, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("tesseract", timeout)
            return b"", b""

        def kill(self):
            self.killed = True

        def wait(self):
            return -9

    process = TimedOutProcess()
    monkeypatch.setattr(service.subprocess, "Popen", lambda *a, **kw: process)
    with pytest.raises(UploadValidationError) as error:
        service._run_bounded_process(["tesseract"], input_bytes=b"image", timeout_seconds=0.01)
    assert error.value.code == "OCR_TIMEOUT"
    assert process.killed


def test_ocr_timeout_cleans_private_temp_and_streams_pdf_from_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import text_extraction_service as service

    image = scanned_image("scan_en.jpg")
    pdf = make_image_pdf([image])
    temp_dirs: list[Path] = []
    monkeypatch.setattr(service.shutil, "which", lambda command: f"/usr/bin/{command}")

    def timeout_on_page(command, *, input_bytes, timeout_seconds):
        temp_dirs.append(Path(command[-1]).parent)
        assert input_bytes == pdf
        raise UploadValidationError("time limit", code="OCR_TIMEOUT")

    monkeypatch.setattr(service, "_run_bounded_process", timeout_on_page)
    with pytest.raises(UploadValidationError) as error:
        service._ocr_pdf(pdf, max_pages=10)

    assert error.value.code == "OCR_TIMEOUT"
    assert len(temp_dirs) == 1
    assert not temp_dirs[0].exists()
