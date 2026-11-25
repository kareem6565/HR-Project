"""OCR text extraction for photographed / scanned CV images (monetization-era feature).

Pluggable provider mirroring the AI provider factory: ``OCR_PROVIDER`` selects the
engine (``tesseract`` CLI by default, ``none`` disables the feature with a clear
error). The provider returns plain text; downstream resume parsing and screening
consume it exactly like PDF/DOCX-extracted text, so no screening logic changes.

Security notes:
- Real magic-byte validation (PNG/JPEG/WEBP) independent of filename or content type.
- The image is written to a private temp file only for the duration of the engine run.
- Engine runs with a hard timeout and no shell; errors surface as structured upload
  errors without leaking server paths.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings
from app.services.errors import (
    UPLOAD_ERROR_CORRUPT,
    UPLOAD_ERROR_NO_TEXT,
    UPLOAD_ERROR_TOO_LARGE,
    UPLOAD_ERROR_UNSUPPORTED_TYPE,
    UploadValidationError,
    ValidationError,
)

logger = logging.getLogger(__name__)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
WEBP_MAGIC_PREFIX = b"RIFF"
WEBP_MAGIC_MARKER = b"WEBP"

IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}


def detect_image_extension(data: bytes) -> str | None:
    """Return the real image format from magic bytes, or None if not an image."""
    if data.startswith(PNG_MAGIC):
        return "png"
    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    if len(data) > 12 and data.startswith(WEBP_MAGIC_PREFIX) and data[8:12] == WEBP_MAGIC_MARKER:
        return "webp"
    return None


def validate_image_upload(data: bytes, *, max_bytes: int) -> str:
    """Validate size and real format; returns the detected extension."""
    if len(data) > max_bytes:
        raise UploadValidationError(
            "The scanned image exceeds the maximum upload size.",
            code=UPLOAD_ERROR_TOO_LARGE,
        )
    extension = detect_image_extension(data)
    if extension is None:
        raise UploadValidationError(
            "Unsupported scan format. Upload a PNG, JPEG, or WEBP image of the CV.",
            code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
        )
    return extension


class OCRProvider(ABC):
    """Extract plain text from one CV image."""

    @abstractmethod
    def extract_text_from_image(self, data: bytes, *, extension: str) -> str:
        """Return the OCR'd text, or raise UploadValidationError."""


class TesseractCLIOCRProvider(OCRProvider):
    """OCR via the local Tesseract CLI (no Python package dependency)."""

    def __init__(self, *, languages: str = "eng", timeout_seconds: int = 30) -> None:
        self._languages = languages
        self._timeout = timeout_seconds

    def extract_text_from_image(self, data: bytes, *, extension: str) -> str:
        suffix = ".jpg" if extension == "jpeg" else f".{extension}"
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(data)
                tmp_path = Path(handle.name)
            result = subprocess.run(
                [
                    "tesseract",
                    str(tmp_path),
                    "stdout",
                    "-l",
                    self._languages,
                    "--psm",
                    "4",
                ],
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            logger.error("tesseract_binary_missing")
            raise ValidationError("OCR engine is not installed on this server.") from exc
        except subprocess.TimeoutExpired as exc:
            raise UploadValidationError(
                "The scan took too long to read. Try a clearer photo.",
                code=UPLOAD_ERROR_CORRUPT,
            ) from exc
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        if result.returncode != 0:
            logger.warning("tesseract_failed exit=%s", result.returncode)
            raise UploadValidationError(
                "The scan could not be read. Try a sharper, well-lit photo.",
                code=UPLOAD_ERROR_CORRUPT,
            )
        text = result.stdout.decode("utf-8", errors="replace").strip()
        if len(text) < 20:
            raise UploadValidationError(
                "No readable text was found in the scan. Try a sharper, well-lit photo.",
                code=UPLOAD_ERROR_NO_TEXT,
            )
        return text


class DisabledOCRProvider(OCRProvider):
    def extract_text_from_image(self, data: bytes, *, extension: str) -> str:
        raise ValidationError("CV scan intake is disabled on this server.")


def get_ocr_provider(app_settings=settings) -> OCRProvider:
    """Factory mirroring the AI provider factory; safe default is disabled."""
    if app_settings.ocr_provider == "tesseract":
        return TesseractCLIOCRProvider(
            languages=app_settings.ocr_languages,
            timeout_seconds=app_settings.ocr_timeout_seconds,
        )
    return DisabledOCRProvider()
