"""Scanned / photographed CV intake (OCR v1).

Accepts a PNG/JPEG/WEBP photo or scan of a CV, OCRs it, and persists a Resume
whose ``extracted_text`` feeds the existing parsing and screening pipeline
unchanged. The original image is stored like any other resume file so HR can
still view or download the source.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from app.models import Candidate, Resume
from app.services.errors import NotFoundError
from app.services.ocr_service import (
    IMAGE_CONTENT_TYPES,
    OCRProvider,
    validate_image_upload,
)
from app.services.resume_service import ResumeService
from app.services.storage_service import StorageProvider


class ResumeScanService:
    def create_from_scan(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        filename: str,
        file_bytes: bytes,
        max_image_bytes: int,
        storage: StorageProvider,
        ocr_provider: OCRProvider,
        checksum: str | None = None,
    ) -> Resume:
        candidate = db.get(Candidate, candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            raise NotFoundError("Candidate was not found.")

        extension = validate_image_upload(file_bytes, max_bytes=max_image_bytes)
        text = ocr_provider.extract_text_from_image(file_bytes, extension=extension)

        resume_id = uuid.uuid4()
        file_uri = ResumeService._save_file(
            storage=storage,
            organization_id=organization_id,
            resume_id=resume_id,
            extension=extension,
            file_bytes=file_bytes,
        )
        try:
            resume = Resume(
                id=resume_id,
                candidate_id=candidate_id,
                file_uri=file_uri,
                original_filename=filename or f"scan.{extension}",
                content_type=IMAGE_CONTENT_TYPES[extension],
                file_size_bytes=len(file_bytes),
                checksum=checksum or hashlib.sha256(file_bytes).hexdigest(),
                extracted_text=text,
                status="text_extracted",
            )
            db.add(resume)
            db.flush()
        except Exception:
            ResumeService._delete_file(storage, file_uri)
            raise
        return resume
