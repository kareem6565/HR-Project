from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CandidateProfile, Resume
from app.services.errors import NotFoundError, ValidationError, VersionConflictError

VALID_STATUSES = frozenset({"extracted", "current", "superseded", "failed"})
VALID_SOURCES = frozenset({"ai_extracted", "hr_corrected", "system_extracted"})


class CandidateProfileService:
    """Deterministic operations for versioned candidate profiles."""

    def create_version(
        self,
        db: Session,
        *,
        resume_id: uuid.UUID,
        status: str,
        source: str,
        profile_data: dict[str, Any],
        provenance: dict[str, Any] | None = None,
        organization_id: uuid.UUID | None = None,
        make_current: bool = True,
    ) -> CandidateProfile:
        """Create a new candidate profile version without mutating history."""
        if status not in VALID_STATUSES:
            raise ValidationError(f"Invalid candidate profile status: {status!r}.")
        if source not in VALID_SOURCES:
            raise ValidationError(f"Invalid candidate profile source: {source!r}.")
        resume = self._get_resume(db, resume_id=resume_id, organization_id=organization_id)

        version_number = self._next_version_number(db, resume_id=resume_id)
        if make_current:
            self._clear_current(db, resume_id=resume_id)

        profile = CandidateProfile(
            resume_id=resume_id,
            version_number=version_number,
            status=status,
            source=source,
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
    ) -> CandidateProfile:
        """Return one candidate profile version by id."""
        profile = db.get(CandidateProfile, profile_id)
        if profile is None:
            raise NotFoundError("CandidateProfile was not found.")
        if (
            organization_id is not None
            and profile.resume.candidate.organization_id != organization_id
        ):
            raise NotFoundError("CandidateProfile was not found.")
        return profile

    def list_versions(
        self,
        db: Session,
        *,
        resume_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> list[CandidateProfile]:
        """Return all candidate profile versions for a resume ordered by version number."""
        resume = self._get_resume(db, resume_id=resume_id, organization_id=organization_id)
        return list(
            db.scalars(
                select(CandidateProfile)
                .where(CandidateProfile.resume_id == resume_id)
                .order_by(CandidateProfile.version_number)
            )
        )

    def get_current_or_latest(
        self,
        db: Session,
        *,
        resume_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> CandidateProfile | None:
        """Return the current candidate profile, falling back to the latest version."""
        versions = self.list_versions(db, resume_id=resume_id, organization_id=organization_id)
        current_versions = [profile for profile in versions if profile.is_current]
        if current_versions:
            return current_versions[-1]
        return versions[-1] if versions else None

    def _get_resume(
        self, db: Session, *, resume_id: uuid.UUID, organization_id: uuid.UUID | None = None
    ) -> Resume:
        resume = db.get(Resume, resume_id)
        if resume is None:
            raise NotFoundError("Resume was not found.")
        if organization_id is not None and resume.candidate.organization_id != organization_id:
            raise NotFoundError("Resume was not found.")
        return resume

    def _next_version_number(self, db: Session, *, resume_id: uuid.UUID) -> int:
        current_max = db.scalar(
            select(func.max(CandidateProfile.version_number)).where(
                CandidateProfile.resume_id == resume_id
            )
        )
        return (current_max or 0) + 1

    def _clear_current(self, db: Session, *, resume_id: uuid.UUID) -> None:
        db.execute(
            update(CandidateProfile)
            .where(CandidateProfile.resume_id == resume_id, CandidateProfile.is_current.is_(True))
            .values(is_current=False)
        )

    def _flush_version(self, db: Session) -> None:
        try:
            db.flush()
        except IntegrityError as error:
            raise VersionConflictError("CandidateProfile version could not be created.") from error
