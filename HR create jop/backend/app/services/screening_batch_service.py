"""Service for asynchronous CV screening batches (HERA Prompt 7).

Manages:
- Bounded batch submission and item registration.
- In-batch and historical duplicate detection via SHA-256 without merging candidates.
- Per-file failure isolation.
- Status queries and progress aggregation scoped to the caller's organization.
- Atomic manual retries for eligible failed items.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Job,
    JobApplication,
    JobProfile,
    Resume,
    ScreeningBatch,
    ScreeningBatchItem,
)
from app.services.errors import (
    UPLOAD_ERROR_UNSUPPORTED_TYPE,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from app.services.job_profile_requirements import get_effective_job_requirements
from app.services.storage_service import StorageProvider
from app.services.upload_stream_service import BoundedFilePayload, detect_resume_format


class ScreeningBatchService:
    """Operations for managing asynchronous screening batches and items."""

    def schedule_public_application(
        self, db: Session, *, application: JobApplication, job: Job, resume: Resume
    ) -> ScreeningBatchItem:
        """Durably enqueue a public application using the existing screening worker."""
        existing = db.scalar(
            select(ScreeningBatchItem).where(
                ScreeningBatchItem.source == "public_application",
                ScreeningBatchItem.application_id == application.id,
            )
        )
        if existing is not None:
            return existing
        profile_id = job.published_job_profile_id
        profile = db.get(JobProfile, profile_id) if profile_id else None
        if profile is None or profile.job_id != job.id or profile.status != "approved":
            raise ValidationError("The published approved JobProfile is unavailable for screening.")
        batch = ScreeningBatch(
            organization_id=job.organization_id,
            job_id=job.id,
            created_by_user_id=None,
            status="queued",
            total_files=1,
            completed_files=0,
            failed_files=0,
        )
        db.add(batch)
        db.flush()
        item = ScreeningBatchItem(
            batch_id=batch.id,
            filename=resume.original_filename or "resume",
            storage_key=resume.file_uri,
            sha256=resume.checksum or "",
            status="queued",
            stage="queued",
            source="public_application",
            job_profile_id=profile.id,
            candidate_id=application.candidate_id,
            resume_id=resume.id,
            application_id=application.id,
            max_attempts=3,
        )
        db.add(item)
        db.flush()
        return item

    @staticmethod
    def reserve_org_batch_slot(db: Session, *, organization_id: uuid.UUID, limit: int) -> None:
        """Serialize per-organization batch admission and enforce the active cap."""
        if db.get_bind().dialect.name == "postgresql":
            db.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(organization_id)))))
        active = (
            db.scalar(
                select(func.count(ScreeningBatch.id)).where(
                    ScreeningBatch.organization_id == organization_id,
                    ScreeningBatch.status.in_(("queued", "running")),
                )
            )
            or 0
        )
        if active >= limit:
            raise ValidationError(
                "This organization already has the maximum number of active screening batches."
            )

    def create_batch(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        user_id: uuid.UUID | None,
        payloads: list[BoundedFilePayload],
        storage: StorageProvider,
        max_concurrent_batches: int = 2,
    ) -> ScreeningBatch:
        """Create a new screening batch and enqueue its items.

        Enforces job tenancy, approved JobProfile presence, duplicate detection,
        and per-file failure isolation. On storage/database failure, created
        files are cleaned up so no orphaned files remain.
        """
        self.reserve_org_batch_slot(
            db, organization_id=organization_id, limit=max_concurrent_batches
        )
        job = db.get(Job, job_id)
        if job is None or job.organization_id != organization_id:
            raise NotFoundError("Job was not found.")

        # Screening requires an approved JobProfile
        approved_profile = None
        for p in job.profiles:
            if p.status == "approved":
                approved_profile = p
                break

        if approved_profile is None:
            raise ValidationError(
                "Screening requires an approved JobProfile. "
                "Extract a profile and approve it in HR review before screening candidates."
            )
        get_effective_job_requirements(job, approved_profile)

        # Preload existing applications and their resume checksums for this job
        stmt = (
            select(Resume.id, JobApplication.id, Resume.checksum)
            .join(JobApplication, JobApplication.resume_id == Resume.id)
            .where(
                JobApplication.job_id == job_id,
                JobApplication.organization_id == organization_id,
                Resume.checksum.is_not(None),
            )
        )
        existing_apps = {row[2]: (row[0], row[1]) for row in db.execute(stmt).all()}

        batch_id = uuid.uuid4()
        batch = ScreeningBatch(
            id=batch_id,
            organization_id=organization_id,
            job_id=job_id,
            created_by_user_id=user_id,
            status="queued",
            total_files=len(payloads),
            completed_files=0,
            failed_files=0,
        )
        db.add(batch)

        created_storage_keys: list[str] = []
        seen_batch_checksums: dict[str, uuid.UUID] = {}

        try:
            for payload in payloads:
                item_id = uuid.uuid4()
                filename = PurePosixPath(payload.filename.strip().replace("\\", "/")).name
                detected_extension = payload.detected_extension or detect_resume_format(
                    payload.data
                )
                extension = detected_extension or "bin"
                if detected_extension:
                    base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
                    suffix = f".{detected_extension}"
                    filename = f"{(base_name or 'resume')[: 255 - len(suffix)]}{suffix}"

                # Save raw upload into batch storage prefix
                storage_key = storage.save_batch_file(
                    organization_id=organization_id,
                    batch_id=batch_id,
                    item_id=item_id,
                    extension=extension,
                    stream=lambda d=payload.data: d,
                )
                created_storage_keys.append(storage_key)

                checksum = payload.checksum
                status = "queued"
                error_code = None
                error_message = None
                duplicate_of_id = None
                existing_res_id = None
                existing_app_id = None

                # 1. Check in-batch duplicate
                if checksum in seen_batch_checksums:
                    status = "duplicate"
                    duplicate_of_id = seen_batch_checksums[checksum]
                    error_message = "Duplicate file content submitted in the same batch."

                # 2. Check pre-existing application for identical file
                elif checksum in existing_apps:
                    status = "duplicate"
                    existing_res_id, existing_app_id = existing_apps[checksum]
                    error_message = "An identical resume has already been applied to this job."

                # 3. Check obvious permanent format invalidity per Prompt 5
                elif detected_extension in ("png", "jpg", "jpeg", "webp"):
                    # Validate the actual image signature; never infer its type from the name.
                    from app.services.ocr_service import detect_image_extension

                    if detect_image_extension(payload.data) != detected_extension:
                        status = "failed"
                        error_code = UPLOAD_ERROR_UNSUPPORTED_TYPE
                        error_message = (
                            "File content does not match a supported image signature "
                            "(PNG/JPEG/WEBP)."
                        )
                    else:
                        seen_batch_checksums[checksum] = item_id
                elif detected_extension not in ("pdf", "docx"):
                    status = "failed"
                    error_code = UPLOAD_ERROR_UNSUPPORTED_TYPE
                    error_message = "File content is not a supported PDF, DOCX, or image document."
                else:
                    seen_batch_checksums[checksum] = item_id

                item = ScreeningBatchItem(
                    id=item_id,
                    batch_id=batch_id,
                    filename=filename,
                    storage_key=storage_key,
                    sha256=checksum,
                    status=status,
                    stage="queued" if status == "queued" else status,
                    error_code=error_code,
                    error_message=error_message,
                    duplicate_of_item_id=duplicate_of_id,
                    resume_id=existing_res_id,
                    application_id=existing_app_id,
                )
                db.add(item)

            db.flush()

            # Refresh batch counters
            self._update_batch_state(batch)
            db.flush()

        except Exception:
            for key in created_storage_keys:
                try:
                    storage.delete(file_uri=key)
                except Exception:
                    pass
            raise

        return batch

    def get_batch(
        self,
        db: Session,
        *,
        batch_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ScreeningBatch:
        """Fetch a screening batch, enforcing organization scope."""
        batch = db.get(ScreeningBatch, batch_id)
        if batch is None or batch.organization_id != organization_id:
            raise NotFoundError("Screening batch was not found.")

        # Ensure summary counters match current items
        self._update_batch_state(batch)
        db.flush()
        return batch

    def retry_item(
        self,
        db: Session,
        *,
        item_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ScreeningBatchItem:
        """Atomically retry an eligible failed screening batch item."""
        item = db.get(ScreeningBatchItem, item_id)
        if item is None or item.batch.organization_id != organization_id:
            raise NotFoundError("Screening batch item was not found.")

        if item.status != "failed":
            raise InvalidStateError(
                f"Cannot retry item in '{item.status}' state. Only failed items may be retried."
            )

        # Atomic reset for retry
        item.status = "queued"
        item.stage = "queued"
        item.claim_token = None
        item.lease_expires_at = None
        item.error_code = None
        item.error_message = None
        item.next_attempt_at = datetime.now(UTC)

        # Allow authorized manual retry even if max automatic attempts reached
        if item.attempts >= item.max_attempts:
            item.max_attempts = item.attempts + 1

        batch = item.batch
        if batch.status in ("completed", "failed"):
            batch.status = "running"
            batch.completed_at = None

        self._update_batch_state(batch)
        db.flush()
        return item

    @staticmethod
    def _update_batch_state(batch: ScreeningBatch) -> None:
        """Derive batch status and counters from its items."""
        items = list(batch.items)
        batch.total_files = len(items)

        completed_count = sum(1 for it in items if it.status in ("done", "duplicate"))
        failed_count = sum(1 for it in items if it.status == "failed")
        running_count = sum(1 for it in items if it.status == "running")
        queued_count = sum(1 for it in items if it.status == "queued")

        batch.completed_files = completed_count
        batch.failed_files = failed_count

        if running_count > 0:
            batch.status = "running"
        elif queued_count > 0:
            batch.status = "queued" if completed_count == 0 and failed_count == 0 else "running"
        else:
            # All items are terminal
            if failed_count == len(items) and len(items) > 0:
                batch.status = "failed"
            else:
                batch.status = "completed"
            if not batch.completed_at:
                batch.completed_at = datetime.now(UTC)
