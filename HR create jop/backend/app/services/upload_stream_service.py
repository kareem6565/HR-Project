"""Bounded chunked streaming service for CV uploads (Prompt 5).

Provides safe streaming of FastAPI `UploadFile` instances in bounded chunks,
enforcing per-file limits, total batch limits, empty file detection, and SHA-256
calculation on the fly with immediate abort upon exceeding limits.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import shutil
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from fastapi import UploadFile

from app.core.config import settings
from app.services.errors import (
    UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED,
    UPLOAD_ERROR_NO_TEXT,
    UPLOAD_ERROR_TOO_LARGE,
    UPLOAD_ERROR_UNSUPPORTED_TYPE,
    UploadValidationError,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024  # 64 KiB chunks


def read_upload_file_bounded(
    file: UploadFile,
    *,
    max_bytes: int | None = None,
    chunk_size: int = CHUNK_SIZE,
) -> tuple[bytes, int, str]:
    """Read an UploadFile incrementally in bounded chunks.

    Returns:
        (file_bytes, byte_count, sha256_checksum)

    Raises:
        UploadValidationError with code="TOO_LARGE" immediately if received bytes exceed max_bytes.
        UploadValidationError with code="NO_TEXT" if received file is empty.
    """
    effective_max = max_bytes if max_bytes is not None else settings.max_upload_bytes
    hasher = hashlib.sha256()
    chunks: list[bytes] = []
    total_bytes = 0

    stream: BinaryIO = file.file
    try:
        stream.seek(0)
    except Exception:
        pass

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > effective_max:
            logger.warning(
                "Upload size limit exceeded for incoming file (%d bytes > %d bytes limit)",
                total_bytes,
                effective_max,
            )
            raise UploadValidationError(
                f"Uploaded file exceeds the maximum allowed size of {effective_max} bytes.",
                code=UPLOAD_ERROR_TOO_LARGE,
            )
        hasher.update(chunk)
        chunks.append(chunk)

    if total_bytes == 0:
        raise UploadValidationError(
            f"Uploaded file {file.filename!r} is empty.",
            code=UPLOAD_ERROR_NO_TEXT,
        )

    file_bytes = b"".join(chunks)
    return file_bytes, total_bytes, hasher.hexdigest()


class BoundedFilePayload:
    """Represents a validated in-memory file payload from a batch read."""

    def __init__(
        self,
        *,
        upload_file: UploadFile,
        filename: str,
        content_type: str,
        data: bytes,
        size: int,
        checksum: str,
        detected_extension: str | None = None,
    ) -> None:
        self.upload_file = upload_file
        self.filename = filename
        self.content_type = content_type
        self.data = data
        self.size = size
        self.checksum = checksum
        self.detected_extension = detected_extension


def read_batch_bounded(
    files: list[UploadFile],
    *,
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_batch_bytes: int | None = None,
    chunk_size: int = CHUNK_SIZE,
) -> list[BoundedFilePayload]:
    """Read a batch of UploadFiles enforcing batch count and payload limits.

    Raises:
        UploadValidationError with code="BATCH_LIMIT_EXCEEDED" if count or total size exceeded.
        UploadValidationError with code="TOO_LARGE" if any single file exceeds max_file_bytes.
    """
    effective_max_files = max_files if max_files is not None else settings.max_batch_files
    effective_max_file_bytes = (
        max_file_bytes if max_file_bytes is not None else settings.max_upload_bytes
    )
    effective_max_batch_bytes = (
        max_batch_bytes if max_batch_bytes is not None else settings.max_batch_bytes
    )

    if not files:
        raise UploadValidationError("No files were uploaded.", code=UPLOAD_ERROR_NO_TEXT)

    if len(files) > effective_max_files:
        logger.warning(
            "Batch file count exceeded: %d files > %d limit",
            len(files),
            effective_max_files,
        )
        raise UploadValidationError(
            f"Batch file count ({len(files)}) exceeds the maximum allowed limit of "
            f"{effective_max_files} files.",
            code=UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED,
        )

    results: list[BoundedFilePayload] = []
    total_batch_bytes = 0

    for idx, f in enumerate(files):
        filename = (f.filename or "").strip()
        if not filename:
            raise UploadValidationError(
                f"File at index {idx} is missing a filename.",
                code=UPLOAD_ERROR_NO_TEXT,
            )

        stream: BinaryIO = f.file
        try:
            stream.seek(0)
        except Exception:
            pass

        hasher = hashlib.sha256()
        file_chunks: list[bytes] = []
        file_bytes_count = 0

        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            chunk_len = len(chunk)
            file_bytes_count += chunk_len
            total_batch_bytes += chunk_len

            if file_bytes_count > effective_max_file_bytes:
                logger.warning(
                    "Single file size limit exceeded in batch for file %r: %d > %d",
                    filename,
                    file_bytes_count,
                    effective_max_file_bytes,
                )
                raise UploadValidationError(
                    f"Uploaded file {filename!r} exceeds the maximum allowed single-file size "
                    f"of {effective_max_file_bytes} bytes.",
                    code=UPLOAD_ERROR_TOO_LARGE,
                )

            if total_batch_bytes > effective_max_batch_bytes:
                logger.warning(
                    "Total batch payload size exceeded: %d > %d",
                    total_batch_bytes,
                    effective_max_batch_bytes,
                )
                raise UploadValidationError(
                    f"Total batch size exceeds the maximum allowed limit of "
                    f"{effective_max_batch_bytes} bytes.",
                    code=UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED,
                )

            hasher.update(chunk)
            file_chunks.append(chunk)

        if file_bytes_count == 0:
            raise UploadValidationError(
                f"Uploaded file {filename!r} is empty.",
                code=UPLOAD_ERROR_NO_TEXT,
            )

        payload_bytes = b"".join(file_chunks)
        results.append(
            BoundedFilePayload(
                upload_file=f,
                filename=filename,
                content_type=f.content_type or "",
                data=payload_bytes,
                size=file_bytes_count,
                checksum=hasher.hexdigest(),
            )
        )

    return results


def detect_resume_format(payload: bytes) -> str | None:
    """Identify supported resumes from contents, including CV scans and DOCX."""
    if payload.startswith(b"%PDF-"):
        return "pdf"
    # Local import avoids making the bounded ZIP reader depend on OCR at import
    # time while still classifying images from their signatures, not filenames.
    from app.services.ocr_service import detect_image_extension

    image_format = detect_image_extension(payload)
    if image_format is not None:
        return image_format
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())
            if {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                return "docx"
    except (zipfile.BadZipFile, OSError):
        return None
    return None


def _normalized_zip_name(name: str) -> str:
    normalized = unicodedata.normalize("NFC", name).replace("\\", "/")
    if not normalized or normalized.startswith("/") or normalized.startswith("//"):
        raise UploadValidationError(
            "ZIP contains an absolute or empty path.", code="INVALID_ARCHIVE"
        )
    parts = PurePosixPath(normalized).parts
    if any(part in ("..", "") for part in parts) or any(":" in part for part in parts):
        raise UploadValidationError("ZIP contains a path traversal entry.", code="INVALID_ARCHIVE")
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
    for part in parts:
        stem = part.rstrip(" .").split(".")[0].casefold()
        if part.endswith((" ", ".")) or stem in reserved:
            raise UploadValidationError(
                "ZIP contains a Windows-reserved path.", code="INVALID_ARCHIVE"
            )
    return "/".join(parts).casefold()


def read_zip_batch_bounded(
    upload: UploadFile,
    *,
    max_entries: int,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
    max_compression_ratio: int,
    max_archive_bytes: int,
    staging_root: str,
    chunk_size: int = CHUNK_SIZE,
) -> list[BoundedFilePayload]:
    """Extract supported entries to private temporary files under actual-byte limits."""
    if shutil.disk_usage(staging_root).free < max_total_bytes + max_archive_bytes + 1024 * 1024:
        raise UploadValidationError(
            "Insufficient free disk space for safe archive extraction.", code="INVALID_ARCHIVE"
        )
    with tempfile.TemporaryDirectory(prefix="hera-zip-", dir=staging_root) as temp_dir:
        archive_path = os.path.join(temp_dir, "upload.zip")
        compressed_size = 0
        try:
            upload.file.seek(0)
        except (AttributeError, OSError):
            pass
        with open(archive_path, "wb") as archive_file:
            while True:
                chunk = upload.file.read(chunk_size)
                if not chunk:
                    break
                compressed_size += len(chunk)
                if compressed_size > max_archive_bytes:
                    raise UploadValidationError(
                        "ZIP upload exceeds the compressed size limit.", code=UPLOAD_ERROR_TOO_LARGE
                    )
                archive_file.write(chunk)
        if compressed_size == 0:
            raise UploadValidationError("ZIP upload is empty.", code="INVALID_ARCHIVE")
        results: list[BoundedFilePayload] = []
        actual_total = 0
        seen_names: set[str] = set()
        file_count = 0
        try:
            with zipfile.ZipFile(archive_path) as archive:
                entries = archive.infolist()
                if not entries or len(entries) > max_entries:
                    raise UploadValidationError(
                        "ZIP entry count is outside the allowed limit.", code="BATCH_LIMIT_EXCEEDED"
                    )
                for index, info in enumerate(entries):
                    normalized = _normalized_zip_name(info.filename)
                    if normalized in seen_names:
                        raise UploadValidationError(
                            "ZIP contains duplicate normalized entry names.", code="INVALID_ARCHIVE"
                        )
                    seen_names.add(normalized)
                    if info.is_dir():
                        continue
                    file_count += 1
                    if file_count > max_files:
                        raise UploadValidationError(
                            "ZIP file count exceeds the batch limit.", code="BATCH_LIMIT_EXCEEDED"
                        )
                    if info.flag_bits & 0x1:
                        raise UploadValidationError(
                            "Encrypted ZIP entries are not accepted.", code="ENCRYPTED"
                        )
                    if stat.S_ISLNK(info.external_attr >> 16):
                        raise UploadValidationError(
                            "ZIP symbolic links are not accepted.", code="INVALID_ARCHIVE"
                        )
                    entry_path = os.path.join(temp_dir, f"entry-{index:05d}.part")
                    checksum = hashlib.sha256()
                    actual_size = 0
                    with archive.open(info, "r") as source, open(entry_path, "wb") as target:
                        while True:
                            data = source.read(chunk_size)
                            if not data:
                                break
                            actual_size += len(data)
                            actual_total += len(data)
                            if actual_size > max_file_bytes:
                                raise UploadValidationError(
                                    "A ZIP entry exceeds the per-file size limit.",
                                    code=UPLOAD_ERROR_TOO_LARGE,
                                )
                            if actual_total > max_total_bytes:
                                raise UploadValidationError(
                                    "ZIP exceeds the total uncompressed size limit.",
                                    code="BATCH_LIMIT_EXCEEDED",
                                )
                            if actual_size / max(info.compress_size, 1) > max_compression_ratio:
                                raise UploadValidationError(
                                    "ZIP entry exceeds the compression-ratio limit.",
                                    code="INVALID_ARCHIVE",
                                )
                            checksum.update(data)
                            target.write(data)
                    if actual_size != info.file_size:
                        raise UploadValidationError(
                            "ZIP entry size does not match its directory record.",
                            code="INVALID_ARCHIVE",
                        )
                    content = Path(entry_path).read_bytes()
                    resume_format = detect_resume_format(content)
                    if resume_format is None and zipfile.is_zipfile(io.BytesIO(content)):
                        try:
                            with zipfile.ZipFile(io.BytesIO(content)) as nested:
                                nested_names = set(nested.namelist())
                        except (
                            zipfile.BadZipFile,
                            OSError,
                            RuntimeError,
                            EOFError,
                            NotImplementedError,
                            zlib.error,
                        ) as exc:
                            raise UploadValidationError(
                                "ZIP contains an invalid nested archive.", code="INVALID_ARCHIVE"
                            ) from exc
                        if {"[Content_Types].xml", "word/document.xml"}.issubset(nested_names):
                            resume_format = "docx"
                        else:
                            raise UploadValidationError(
                                "Nested archives are not accepted.", code="INVALID_ARCHIVE"
                            )
                    if resume_format is None:
                        raise UploadValidationError(
                            "ZIP contains an unsupported file based on its contents.",
                            code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
                        )
                    original_name = PurePosixPath(info.filename.replace("\\", "/")).name
                    results.append(
                        BoundedFilePayload(
                            upload_file=upload,
                            filename=original_name,
                            content_type="",
                            data=content,
                            size=actual_size,
                            checksum=checksum.hexdigest(),
                            detected_extension=resume_format,
                        )
                    )
        except (
            zipfile.BadZipFile,
            OSError,
            RuntimeError,
            EOFError,
            NotImplementedError,
            zlib.error,
        ) as exc:
            raise UploadValidationError(
                "Uploaded file is not a valid ZIP archive.", code="INVALID_ARCHIVE"
            ) from exc
        if not results:
            raise UploadValidationError(
                "ZIP contains no supported resume files.", code=UPLOAD_ERROR_NO_TEXT
            )
        return results
