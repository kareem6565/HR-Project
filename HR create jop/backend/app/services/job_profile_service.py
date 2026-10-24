from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Job, JobProfile, User
from app.services.errors import (
    InvalidStateError,
    NotFoundError,
    ValidationError,
    VersionConflictError,
)

VALID_STATUSES = frozenset({"draft", "approved", "superseded"})
VALID_SOURCES = frozenset({"ai_extracted", "hr_edited", "hr_created"})


class JobProfileService:
    """Deterministic lifecycle operations for versioned job profiles."""

    def create_version(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        status: str,
        source: str,
        profile_data: dict[str, Any],
        raw_input_snapshot: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        organization_id: uuid.UUID | None = None,
        make_current: bool = True,
    ) -> JobProfile:
        """Create a new job profile version without overwriting prior versions."""
        if status not in VALID_STATUSES:
            raise ValidationError(f"Invalid job profile status: {status!r}.")
        if source not in VALID_SOURCES:
            raise ValidationError(f"Invalid job profile source: {source!r}.")
        job = self._get_job(db, job_id=job_id, organization_id=organization_id)

        version_number = self._next_version_number(db, job_id=job_id)
        if make_current:
            self._clear_current(db, job_id=job_id)

        profile = JobProfile(
            job_id=job_id,
            version_number=version_number,
            status=status,
            source=source,
            raw_input_snapshot=raw_input_snapshot,
            profile_data=profile_data,
            provenance=provenance,
            is_current=make_current,
        )
        db.add(profile)
        self._flush_version(db)
        return profile

    def get_version(
        self,
        db: Session,
        *,
        profile_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> JobProfile:
        """Return one job profile version by id."""
        profile = db.get(JobProfile, profile_id)
        if profile is None:
            raise NotFoundError("JobProfile was not found.")
        if organization_id is not None and profile.job.organization_id != organization_id:
            raise NotFoundError("JobProfile was not found.")
        return profile

    def list_versions(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> list[JobProfile]:
        """Return all profile versions for a job ordered by version number."""
        job = self._get_job(db, job_id=job_id, organization_id=organization_id)
        return list(
            db.scalars(
                select(JobProfile)
                .where(JobProfile.job_id == job_id)
                .order_by(JobProfile.version_number)
            )
        )

    def approve(
        self,
        db: Session,
        *,
        profile_id: uuid.UUID,
        approved_by_user_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
        approved_at: datetime | None = None,
    ) -> JobProfile:
        """Approve a job profile version while preserving its profile data."""
        profile = self.get_version(db, profile_id=profile_id, organization_id=organization_id)
        user = db.get(User, approved_by_user_id)
        if user is None:
            raise NotFoundError("Approving user was not found.")
        if user.organization_id != profile.job.organization_id:
            raise NotFoundError("JobProfile was not found.")
        if profile.status == "approved":
            raise InvalidStateError("JobProfile is already approved.")

        self._clear_current(db, job_id=profile.job_id)
        profile.status = "approved"
        profile.approved_by_user_id = approved_by_user_id
        profile.approved_at = approved_at or datetime.now(UTC)
        profile.is_current = True

        from app.services.audit_service import AuditService

        AuditService().log_event(
            db,
            action="job_profile.approved",
            entity_type="job_profile",
            organization_id=profile.job.organization_id,
            actor_user_id=approved_by_user_id,
            entity_id=profile.id,
            metadata={
                "job_id": str(profile.job_id),
                "version_number": profile.version_number,
                "status": profile.status,
            },
            flush=False,
        )

        db.flush()
        return profile

    def get_current_or_latest(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> JobProfile | None:
        """Return the current job profile, falling back to the latest version."""
        versions = self.list_versions(db, job_id=job_id, organization_id=organization_id)
        current_versions = [profile for profile in versions if profile.is_current]
        if current_versions:
            return current_versions[-1]
        return versions[-1] if versions else None

    def _get_job(
        self, db: Session, *, job_id: uuid.UUID, organization_id: uuid.UUID | None = None
    ) -> Job:
        job = db.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job was not found.")
        if organization_id is not None and job.organization_id != organization_id:
            raise NotFoundError("Job was not found.")
        return job

    def _next_version_number(self, db: Session, *, job_id: uuid.UUID) -> int:
        current_max = db.scalar(
            select(func.max(JobProfile.version_number)).where(JobProfile.job_id == job_id)
        )
        return (current_max or 0) + 1

    def _clear_current(self, db: Session, *, job_id: uuid.UUID) -> None:
        db.execute(
            update(JobProfile)
            .where(JobProfile.job_id == job_id, JobProfile.is_current.is_(True))
            .values(is_current=False)
        )

    def _flush_version(self, db: Session) -> None:
        try:
            db.flush()
        except IntegrityError as error:
            raise VersionConflictError("JobProfile version could not be created.") from error
