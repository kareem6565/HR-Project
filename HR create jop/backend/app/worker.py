"""PostgreSQL-backed asynchronous screening worker (HERA Prompt 7).

Provides durable, atomic work claiming via PostgreSQL FOR UPDATE SKIP LOCKED,
per-file failure isolation, idempotent execution, lease recovery, exponential
backoff for transient failures, and safe storage cleanup.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
import signal
import sys
import threading
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.providers import get_provider
from app.ai.workflows import CandidateEvaluationWorkflow, CandidateProfileExtractionWorkflow
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import (
    Candidate,
    CandidateEvaluation,
    Job,
    JobApplication,
    JobProfile,
    Resume,
    ScreeningBatch,
    ScreeningBatchItem,
)
from app.services.candidate_service import CandidateService
from app.services.errors import UploadValidationError
from app.services.job_application_service import JobApplicationService
from app.services.resume_details_service import derive_screening_payloads
from app.services.screening_batch_service import ScreeningBatchService
from app.services.storage_service import LocalFileSystemStorage, StorageProvider
from app.services.text_extraction_service import extract_text

logger = logging.getLogger("app.worker")


class ScreeningWorker:
    """Worker instance processing queued screening batch items."""

    def __init__(
        self,
        *,
        storage: StorageProvider | None = None,
        lease_seconds: int = 300,
        initial_retry_delay_seconds: int = 30,
        session_factory: Any | None = None,
    ) -> None:
        self.storage = storage or LocalFileSystemStorage(settings.storage_root_dir)
        self.lease_seconds = lease_seconds
        self.initial_retry_delay_seconds = initial_retry_delay_seconds
        self.session_factory = session_factory or SessionLocal
        self.should_stop = False
        self.stop_event = threading.Event()

    def request_shutdown(self, signum=None, frame=None) -> None:
        logger.info("Worker shutdown signal received. Finishing active item and stopping...")
        self.should_stop = True
        self.stop_event.set()

    def claim_next_item(self, db: Session) -> tuple[uuid.UUID, str] | None:
        """Atomically claim one eligible queued item in a short committed transaction."""
        now = datetime.now(UTC)
        stmt = (
            select(ScreeningBatchItem)
            .where(
                ScreeningBatchItem.status == "queued",
                ScreeningBatchItem.next_attempt_at <= now,
            )
            .order_by(ScreeningBatchItem.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        item = db.execute(stmt).scalars().first()
        if item is None:
            return None

        claim_token = str(uuid.uuid4())
        item.status = "running"
        item.stage = "claimed"
        item.claim_token = claim_token
        item.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
        item.attempts += 1
        item.updated_at = now

        batch = item.batch
        if batch.status != "running":
            batch.status = "running"

        db.commit()
        return item.id, claim_token

    def recover_stale_leases(self, db: Session) -> int:
        """Recover expired claims whose workers crashed or stalled."""
        now = datetime.now(UTC)
        stmt = (
            select(ScreeningBatchItem)
            .where(
                ScreeningBatchItem.status == "running",
                ScreeningBatchItem.lease_expires_at < now,
            )
            .with_for_update(skip_locked=True)
        )
        stale_items = db.execute(stmt).scalars().all()
        recovered = 0
        for item in stale_items:
            if item.attempts < item.max_attempts:
                item.status = "queued"
                item.stage = "queued"
                item.claim_token = None
                item.lease_expires_at = None
                item.next_attempt_at = now
            else:
                item.status = "failed"
                item.stage = "failed"
                item.error_code = "LEASE_EXPIRED"
                item.error_message = "Worker lease expired and max retry attempts were exceeded."
                item.claim_token = None
                item.lease_expires_at = None

            recovered += 1

        if recovered > 0:
            db.commit()
            logger.warning("Recovered %d stale screening batch items.", recovered)
        return recovered

    def process_item(
        self,
        db: Session,
        item_id: uuid.UUID,
        claim_token: str,
    ) -> bool:
        """Process a single claimed item end-to-end with failure isolation."""
        item = db.get(ScreeningBatchItem, item_id)
        if (
            item is None
            or item.claim_token != claim_token
            or item.status != "running"
        ):
            logger.warning("Claim lost or item reclaimed by another worker: %s", item_id)
            return False

        batch = item.batch
        org_id = batch.organization_id
        job_id = batch.job_id
        job = db.get(Job, job_id)
        if job is None or job.organization_id != org_id:
            self._record_permanent_failure(
                item_id, claim_token, "JOB_NOT_FOUND", "Associated job does not exist.", db=db
            )
            return False

        approved_profile = None
        for p in job.profiles:
            if p.status == "approved":
                approved_profile = p
                break

        if approved_profile is None:
            self._record_permanent_failure(
                item_id,
                claim_token,
                "JOB_PROFILE_MISSING",
                "Job has no approved JobProfile.",
                db=db,
            )
            return False

        # Read stored batch file
        try:
            raw_bytes = self.storage.read(file_uri=item.storage_key)
        except Exception as exc:
            logger.error("Failed to read stored batch file for item %s: %s", item_id, type(exc).__name__)
            self._record_permanent_failure(
                item_id, claim_token, "STORAGE_READ_FAILED", "Failed to read stored CV file.", db=db
            )
            return False

        # Extract text and validate format
        try:
            text = extract_text(
                raw_bytes,
                filename=item.filename,
                max_pdf_pages=settings.max_pdf_pages,
                max_docx_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
                max_docx_entries=settings.max_docx_entries,
            )
        except UploadValidationError as exc:
            logger.warning("Validation failed for item %s: %s (%s)", item_id, exc.code, exc)
            self._record_permanent_failure(
                item_id, claim_token, exc.code, str(exc), db=db
            )
            return False
        except Exception as exc:
            logger.warning("Unexpected extraction error for item %s: %s", item_id, type(exc).__name__)
            self._record_permanent_failure(
                item_id, claim_token, "CORRUPT", "Document extraction failed.", db=db
            )
            return False

        # Execute candidate creation, profile extraction, and evaluation pipeline
        created_resume_uri = None
        try:
            with db.begin_nested():
                # Verify claim token still valid before writing records
                if item.claim_token != claim_token:
                    raise RuntimeError("Claim token preempted during processing.")

                # 1. Candidate
                candidate_name = self._candidate_name_from_filename(item.filename)
                candidate = CandidateService().create(
                    db,
                    organization_id=org_id,
                    full_name=candidate_name,
                )

                # 2. Permanent resume storage
                resume_id = uuid.uuid4()
                extension = Path(item.filename).suffix.lower().lstrip(".")
                created_resume_uri = self.storage.save(
                    organization_id=org_id,
                    resume_id=resume_id,
                    extension=extension,
                    stream=lambda: raw_bytes,
                )
                resume = Resume(
                    id=resume_id,
                    candidate_id=candidate.id,
                    file_uri=created_resume_uri,
                    original_filename=item.filename,
                    content_type="application/pdf" if extension == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    file_size_bytes=len(raw_bytes),
                    checksum=item.sha256,
                    extracted_text=text,
                    status="text_extracted",
                )
                db.add(resume)
                db.flush()

                # 3. Profile extraction
                profile_payload, evidence_payload, explanation_payload = derive_screening_payloads(
                    full_name=candidate.full_name,
                    job_title=job.title,
                    resume_text=resume.extracted_text,
                    requirements=approved_profile.profile_data.get("requirements") or [],
                )
                profile_extractor = get_provider(
                    settings,
                    structured_payload=profile_payload,
                )
                CandidateProfileExtractionWorkflow(profile_extractor).run(
                    db,
                    resume_id=resume.id,
                    organization_id=org_id,
                    resume_text=resume.extracted_text,
                )

                # 4. Job application
                application = JobApplicationService().create(
                    db,
                    organization_id=org_id,
                    job_id=job.id,
                    candidate_id=candidate.id,
                    resume_id=resume.id,
                )

                # 5. Candidate evaluation
                eval_result = CandidateEvaluationWorkflow(
                    evidence_provider=get_provider(
                        settings,
                        structured_payload=evidence_payload,
                    ),
                    explanation_provider=get_provider(
                        settings,
                        structured_payload=explanation_payload,
                    ),
                ).run(
                    db,
                    job_application_id=application.id,
                    organization_id=org_id,
                )

                # Re-verify claim token before finalizing item state
                if item.claim_token != claim_token:
                    raise RuntimeError("Claim token preempted before commit.")

                # 6. Mark item done
                item.candidate_id = candidate.id
                item.resume_id = resume.id
                item.application_id = application.id
                item.evaluation_id = eval_result.evaluation_id
                item.status = "done"
                item.stage = "done"
                item.claim_token = None
                item.lease_expires_at = None
                item.error_code = None
                item.error_message = None

                ScreeningBatchService._update_batch_state(batch)

            db.commit()
            logger.info("Successfully processed batch item %s for candidate %s", item_id, candidate.id)
            return True

        except Exception as exc:
            db.rollback()
            if created_resume_uri:
                try:
                    self.storage.delete(file_uri=created_resume_uri)
                except Exception:
                    pass

            logger.error("Transient error during item %s execution: %s", item_id, type(exc).__name__, exc_info=True)
            self._handle_transient_failure(item_id, claim_token, str(type(exc).__name__), db=db)
            return False

    def _record_permanent_failure(
        self,
        item_id: uuid.UUID,
        claim_token: str,
        error_code: str,
        error_message: str,
        db: Session | None = None,
    ) -> None:
        """Mark an item permanently failed in a short committed transaction."""
        def _apply(session: Session) -> None:
            item = session.get(ScreeningBatchItem, item_id)
            if item and item.claim_token == claim_token:
                item.status = "failed"
                item.stage = "failed"
                item.error_code = error_code
                item.error_message = error_message
                item.claim_token = None
                item.lease_expires_at = None
                ScreeningBatchService._update_batch_state(item.batch)
                session.commit()

        if db is not None:
            _apply(db)
        else:
            with self.session_factory() as session:
                _apply(session)

    def _handle_transient_failure(
        self,
        item_id: uuid.UUID,
        claim_token: str,
        reason: str,
        db: Session | None = None,
    ) -> None:
        """Requeue an item with exponential backoff or fail if attempts exhausted."""
        def _apply(session: Session) -> None:
            item = session.get(ScreeningBatchItem, item_id)
            if item and item.claim_token == claim_token:
                if item.attempts < item.max_attempts:
                    delay = self.initial_retry_delay_seconds * (2 ** max(0, item.attempts - 1))
                    item.status = "queued"
                    item.stage = "retry_scheduled"
                    item.claim_token = None
                    item.lease_expires_at = None
                    item.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
                    logger.info("Requeued item %s with %ds backoff delay (attempt %d/%d)", item_id, delay, item.attempts, item.max_attempts)
                else:
                    item.status = "failed"
                    item.stage = "failed"
                    item.error_code = "MAX_ATTEMPTS_EXCEEDED"
                    item.error_message = f"Exceeded maximum attempts ({item.max_attempts}). Last error: {reason}"
                    item.claim_token = None
                    item.lease_expires_at = None
                    logger.warning("Item %s exhausted max attempts and failed.", item_id)

                ScreeningBatchService._update_batch_state(item.batch)
                session.commit()

        if db is not None:
            _apply(db)
        else:
            with self.session_factory() as session:
                _apply(session)

    def run_once(self) -> bool:
        """Execute one processing cycle: recover leases then process one item."""
        with self.session_factory() as db:
            self.recover_stale_leases(db)
            claimed = self.claim_next_item(db)

        if claimed is None:
            return False

        item_id, claim_token = claimed
        with self.session_factory() as db:
            self.process_item(db, item_id, claim_token)
        return True

    def run_loop(self, poll_interval_seconds: float = 2.0) -> None:
        """Run the worker loop continuously until shutdown is requested."""
        logger.info("Screening worker started polling loop.")
        while not self.should_stop and not self.stop_event.is_set():
            try:
                processed = self.run_once()
                if not processed:
                    self.stop_event.wait(timeout=poll_interval_seconds)
            except Exception as exc:
                logger.error("Unhandled error in worker loop: %s", type(exc).__name__, exc_info=True)
                self.stop_event.wait(timeout=poll_interval_seconds)

        logger.info("Screening worker loop exited cleanly.")

    @staticmethod
    def _candidate_name_from_filename(filename: str) -> str:
        stem = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
        words = [word for word in stem.split() if word]
        if not words:
            return "Screened Candidate"
        cleaned = [
            word[:1].upper() + word[1:] if word else word
            for word in words
            if any(char.isalnum() for char in word)
        ]
        if not cleaned:
            return "Screened Candidate"
        return " ".join(cleaned)


def main() -> None:
    """CLI entrypoint for running the worker standalone."""
    parser = argparse.ArgumentParser(description="HERA Screening Batch Worker")
    parser.add_argument("--once", action="store_true", help="Process at most one item and exit.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    args = parser.parse_args()

    worker = ScreeningWorker()

    # Register graceful shutdown signals
    signal.signal(signal.SIGINT, worker.request_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, worker.request_shutdown)

    if args.once:
        worker.run_once()
    else:
        worker.run_loop(poll_interval_seconds=args.interval)


if __name__ == "__main__":
    main()
