from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from app.models import Candidate, Resume
from app.services.errors import (
    UPLOAD_ERROR_TOO_LARGE,
    UPLOAD_ERROR_UNSUPPORTED_TYPE,
    InvalidStateError,
    NotFoundError,
    UploadValidationError,
    ValidationError,
)
from app.services.storage_service import StorageProvider
from app.services.text_extraction_service import (
    DOCX_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    PDF_MAGIC,
    ZIP_MAGIC,
    extract_text,
)


class ResumeService:
    """Minimal resume CRUD and upload operations."""

    def create(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        file_uri: str,
        original_filename: str | None = None,
        content_type: str | None = None,
        file_size_bytes: int | None = None,
    ) -> Resume:
        """Create a new resume for a candidate."""
        candidate = db.get(Candidate, candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            raise NotFoundError("Candidate was not found.")
        resume = Resume(
            candidate_id=candidate_id,
            file_uri=file_uri,
            original_filename=original_filename,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
        )
        db.add(resume)
        db.flush()
        return resume

    def create_from_upload(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        max_upload_bytes: int,
        storage: StorageProvider,
        checksum: str | None = None,
    ) -> Resume:
        """Store an uploaded resume file, extract its text, and persist metadata.

        Persists only the file path and metadata; raw file bytes never enter the
        database. On any failure after the file is written to disk, the stored
        file is deleted so no orphaned files remain. The caller owns the
        transaction and rolls back on error.
        """
        self._validate_file(
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
            max_upload_bytes=max_upload_bytes,
        )

        candidate = db.get(Candidate, candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            raise NotFoundError("Candidate was not found.")

        extension = filename.rsplit(".", 1)[-1].lower()
        resume_id = uuid.uuid4()
        file_uri = self._save_file(
            storage=storage,
            organization_id=organization_id,
            resume_id=resume_id,
            extension=extension,
            file_bytes=file_bytes,
        )

        # Once the file is on disk, any subsequent failure deletes it so no
        # orphaned file remains. The caller rolls back the DB transaction.
        try:
            text = extract_text(file_bytes, filename=filename)
            digest = checksum or hashlib.sha256(file_bytes).hexdigest()
            resume = Resume(
                id=resume_id,
                candidate_id=candidate_id,
                file_uri=file_uri,
                original_filename=filename,
                content_type=content_type,
                file_size_bytes=len(file_bytes),
                checksum=digest,
                extracted_text=text,
                status="text_extracted",
            )
            db.add(resume)
            db.flush()
        except Exception:
            self._delete_file(storage, file_uri)
            raise

        return resume

    def list_for_candidate(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[Resume]:
        """Return a candidate's resumes, enforcing organization scope."""
        candidate = db.get(Candidate, candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            raise NotFoundError("Candidate was not found.")
        return list(candidate.resumes)

    def get(
        self,
        db: Session,
        *,
        resume_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Resume:
        """Return one resume by id, enforcing organization scope via candidate."""
        resume = db.get(Resume, resume_id)
        if resume is None or resume.candidate.organization_id != organization_id:
            raise NotFoundError("Resume was not found.")
        return resume

    def get_extracted_text(
        self,
        db: Session,
        *,
        resume_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> str:
        """Return the extracted text for a resume, for internal workflow use only.

        Enforces organization scope and requires the resume to have extracted
        text available.
        """
        resume = self.get(db, resume_id=resume_id, organization_id=organization_id)
        if not resume.extracted_text:
            raise InvalidStateError("Resume has no extracted text available.")
        return resume.extracted_text

    @staticmethod
    def _validate_file(
        *,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        max_upload_bytes: int,
    ) -> None:
        if len(file_bytes) > max_upload_bytes:
            raise UploadValidationError(
                f"Uploaded file exceeds the maximum size of {max_upload_bytes} bytes.",
                code=UPLOAD_ERROR_TOO_LARGE,
            )

        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        type_map = {"pdf": PDF_CONTENT_TYPE, "docx": DOCX_CONTENT_TYPE}
        expected_type = type_map.get(extension)
        if expected_type is None:
            raise UploadValidationError(
                "Unsupported file type: "
                f"{extension or 'unknown'!r}. Only .pdf and .docx are allowed.",
                code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
            )
        if content_type is None or content_type.lower() != expected_type:
            raise UploadValidationError(
                f"Content type {content_type!r} does not match the file extension .{extension}.",
                code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
            )

        # File signature validation
        if extension == "pdf" and not file_bytes.startswith(PDF_MAGIC):
            raise UploadValidationError(
                "File content does not match PDF signature.",
                code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
            )
        if extension == "docx" and not file_bytes.startswith(ZIP_MAGIC):
            raise UploadValidationError(
                "File content does not match DOCX/ZIP signature.",
                code=UPLOAD_ERROR_UNSUPPORTED_TYPE,
            )

    @staticmethod
    def _save_file(
        *,
        storage: StorageProvider,
        organization_id: uuid.UUID,
        resume_id: uuid.UUID,
        extension: str,
        file_bytes: bytes,
    ) -> str:
        return storage.save(
            organization_id=organization_id,
            resume_id=resume_id,
            extension=extension,
            stream=lambda: file_bytes,
        )

    @staticmethod
    def _delete_file(storage: StorageProvider, file_uri: str) -> None:
        storage.delete(file_uri=file_uri)
