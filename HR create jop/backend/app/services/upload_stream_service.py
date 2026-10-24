"""Bounded chunked streaming service for CV uploads (Prompt 5).

Provides safe streaming of FastAPI `UploadFile` instances in bounded chunks,
enforcing per-file limits, total batch limits, empty file detection, and SHA-256
calculation on the fly with immediate abort upon exceeding limits.
"""

from __future__ import annotations

import hashlib
import logging
from typing import BinaryIO

from fastapi import UploadFile

from app.core.config import settings
from app.services.errors import (
    UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED,
    UPLOAD_ERROR_NO_TEXT,
    UPLOAD_ERROR_TOO_LARGE,
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
                "Upload size limit exceeded for file: %s (%d bytes > %d bytes limit)",
                file.filename,
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
    ) -> None:
        self.upload_file = upload_file
        self.filename = filename
        self.content_type = content_type
        self.data = data
        self.size = size
        self.checksum = checksum


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
            f"Batch file count ({len(files)}) exceeds the maximum allowed limit of {effective_max_files} files.",
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
                    f"Uploaded file {filename!r} exceeds the maximum allowed single-file size of {effective_max_file_bytes} bytes.",
                    code=UPLOAD_ERROR_TOO_LARGE,
                )

            if total_batch_bytes > effective_max_batch_bytes:
                logger.warning(
                    "Total batch payload size exceeded: %d > %d",
                    total_batch_bytes,
                    effective_max_batch_bytes,
                )
                raise UploadValidationError(
                    f"Total batch size exceeds the maximum allowed limit of {effective_max_batch_bytes} bytes.",
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
