from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Job, JobApplication, JobProfile
from app.services.errors import InvalidStateError, NotFoundError, ValidationError


class JobService:
    """Minimal job CRUD operations."""

    def list(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
    ) -> list[Job]:
        """Return the organization's jobs, newest first."""
        stmt = (
            select(Job)
            .where(Job.organization_id == organization_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
        )
        return list(db.scalars(stmt).all())

    def create(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        title: str,
        raw_description: str | None = None,
        description_text: str | None = None,
        status: str = "draft",
        department: str | None = None,
        location: str | None = None,
        job_type: str | None = None,
        work_mode: str | None = None,
        experience: str | None = None,
        requirements: list[str] | None = None,
        required_skills: list[str] | None = None,
        created_by_user_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> Job:
        """Create a draft vacancy, replaying requests with the same scoped key."""
        if idempotency_key:
            existing = db.scalar(
                select(Job).where(
                    Job.organization_id == organization_id,
                    Job.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return existing
        if status != "draft":
            raise ValidationError("New vacancies must be saved as drafts before activation.")
        job = Job(
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            title=title,
            raw_description=raw_description,
            description_text=description_text,
            status=status,
            department=department,
            location=location,
            job_type=job_type,
            work_mode=work_mode,
            experience=experience,
            requirements=requirements or [],
            required_skills=required_skills or [],
            idempotency_key=idempotency_key,
        )
        db.add(job)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            if idempotency_key:
                replay = db.scalar(
                    select(Job).where(
                        Job.organization_id == organization_id,
                        Job.idempotency_key == idempotency_key,
                    )
                )
                if replay is not None:
                    return replay
            raise
        return job

    def get(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Job:
        """Return one job by id, enforcing organization scope."""
        job = db.get(Job, job_id)
        if job is None or job.organization_id != organization_id:
            raise NotFoundError("Job was not found.")
        return job

    def delete(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        """Hard-delete a job, rejecting jobs that are still in use.

        Applications and profiles reference the job with RESTRICT FKs, so a
        job that has candidates or a profile cannot be removed.
        """
        job = self.get(db, job_id=job_id, organization_id=organization_id)
        app_count = db.scalar(
            select(func.count()).select_from(JobApplication).where(JobApplication.job_id == job_id)
        )
        profile_count = db.scalar(
            select(func.count()).select_from(JobProfile).where(JobProfile.job_id == job_id)
        )
        if app_count or profile_count:
            raise InvalidStateError(
                "This job has candidates or a profile attached and cannot be "
                "deleted. Close it instead."
            )
        db.delete(job)
        db.flush()

    def update(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        title: str | None = None,
        raw_description: str | None = None,
        description_text: str | None = None,
        status: str | None = None,
        department: str | None = None,
        location: str | None = None,
        job_type: str | None = None,
        work_mode: str | None = None,
        clear_work_mode: bool = False,
        experience: str | None = None,
        requirements: list[str] | None = None,
        required_skills: list[str] | None = None,
    ) -> Job:
        """Update a job's mutable fields."""
        job = self.get(db, job_id=job_id, organization_id=organization_id)
        if title is not None:
            job.title = title
        if raw_description is not None:
            job.raw_description = raw_description
        if description_text is not None:
            job.description_text = description_text
        if department is not None:
            job.department = department
        if location is not None:
            job.location = location
        if job_type is not None:
            job.job_type = job_type
        if clear_work_mode:
            job.work_mode = None
        elif work_mode is not None:
            job.work_mode = work_mode
        if experience is not None:
            job.experience = experience
        if requirements is not None:
            job.requirements = requirements
        if required_skills is not None:
            job.required_skills = required_skills
        if status is not None:
            if status == "active":
                self.validate_for_activation(db, job)
            job.status = status
        db.flush()
        return job

    def publish(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
    ) -> Job:
        job = self.get(db, job_id=job_id, organization_id=organization_id)
        if job.publication_status == "published":
            return job
        if job.status != "active":
            raise InvalidStateError(
                "Activate this vacancy internally before publishing it publicly."
            )
        self.validate_required_vacancy_fields(job)
        profile = db.scalar(
            select(JobProfile)
            .where(JobProfile.job_id == job.id, JobProfile.status == "approved")
            .order_by(JobProfile.is_current.desc(), JobProfile.version_number.desc())
        )
        if profile is None:
            raise InvalidStateError(
                "Approve a job requirements profile before publishing this vacancy."
            )
        if not job.public_id:
            job.public_id = secrets.token_urlsafe(24)
        job.published_job_profile_id = profile.id
        job.publication_status = "published"
        job.published_at = datetime.now(UTC)
        job.public_closed_at = None
        db.flush()
        self._audit_publication(db, job, "job.publication.published", actor_user_id)
        return job

    def close_publication(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
    ) -> Job:
        job = self.get(db, job_id=job_id, organization_id=organization_id)
        if job.publication_status == "unpublished":
            raise InvalidStateError("This vacancy has not been published.")
        if job.publication_status != "closed":
            job.publication_status = "closed"
            job.public_closed_at = datetime.now(UTC)
            db.flush()
            self._audit_publication(db, job, "job.publication.closed", actor_user_id)
        return job

    @staticmethod
    def public_details(db: Session, *, public_id: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-]{32}", public_id or ""):
            raise NotFoundError("Public job was not found.")
        job = db.scalar(select(Job).where(Job.public_id == public_id))
        if job is None or job.publication_status == "unpublished":
            raise NotFoundError("Public job was not found.")
        profile = (
            db.get(JobProfile, job.published_job_profile_id)
            if job.published_job_profile_id
            else None
        )
        requirements = (profile.profile_data or {}).get("requirements", []) if profile else []
        requirements = [
            item
            for item in requirements
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        responsibilities = [
            item["text"] for item in requirements if item.get("dimension") == "responsibility"
        ]
        required = [
            item["text"]
            for item in requirements
            if item.get("category") == "must_have" and item.get("dimension") != "responsibility"
        ]
        other = [
            item["text"]
            for item in requirements
            if item.get("category") == "important" and item.get("dimension") != "responsibility"
        ]
        preferred = [
            item["text"]
            for item in requirements
            if item.get("category") == "nice_to_have" and item.get("dimension") != "responsibility"
        ]
        return {
            "title": job.title,
            "organization_name": job.organization.name,
            "location": job.location,
            "job_type": job.job_type,
            "work_mode": job.work_mode,
            "experience": job.experience,
            "description": job.description_text or job.raw_description or job.source_file_text,
            "responsibilities": responsibilities,
            "required_qualifications": required,
            "other_qualifications": other,
            "preferred_qualifications": preferred,
            "publication_status": job.publication_status,
            "accepting_applications": job.publication_status == "published",
        }

    @staticmethod
    def _audit_publication(
        db: Session, job: Job, action: str, actor_user_id: uuid.UUID | None
    ) -> None:
        from app.services.audit_service import AuditService

        AuditService().log_event(
            db,
            action=action,
            entity_type="job",
            organization_id=job.organization_id,
            actor_user_id=actor_user_id,
            entity_id=job.id,
            metadata={"publication_status": job.publication_status},
            flush=False,
        )

    def validate_for_activation(self, db: Session, job: Job) -> None:
        """Ensure a vacancy is complete and has an approved evaluation profile."""
        self.validate_required_vacancy_fields(job)
        has_approved_profile = db.scalar(
            select(func.count())
            .select_from(JobProfile)
            .where(JobProfile.job_id == job.id, JobProfile.status == "approved")
        )
        if not has_approved_profile:
            raise InvalidStateError(
                "Approve a reviewed job requirements profile before activating this vacancy."
            )

    @staticmethod
    def validate_required_vacancy_fields(job: Job) -> None:
        """Validate title, source description, and required specifications."""
        missing = []
        if not job.title.strip():
            missing.append("job title")
        description = (
            job.description_text if job.description_text is not None else job.raw_description
        )
        if not (description or job.source_file_text or "").strip():
            missing.append("job description")
        if not (job.job_type or "").strip():
            missing.append("employment type")
        if not (job.experience or "").strip():
            missing.append("required experience")
        if not (job.requirements or job.required_skills):
            missing.append("at least one requirement or required skill")
        if missing:
            raise ValidationError(
                "Complete these required fields before activation: " + ", ".join(missing) + "."
            )
