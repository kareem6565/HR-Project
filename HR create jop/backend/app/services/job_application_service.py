from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobApplication
from app.services.errors import NotFoundError, ValidationError
from app.services.job_application_validation import validate_job_application_consistency


class JobApplicationService:
    """Minimal job application CRUD operations."""

    def create(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        resume_id: uuid.UUID,
    ) -> JobApplication:
        """Create a new job application after validating cross-entity consistency."""
        from app.models import Candidate, Job, Resume

        job = db.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job was not found.")
        candidate = db.get(Candidate, candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate was not found.")
        resume = db.get(Resume, resume_id)
        if resume is None:
            raise NotFoundError("Resume was not found.")

        validate_job_application_consistency(
            organization_id=organization_id,
            job=job,
            candidate=candidate,
            resume=resume,
        )

        application = JobApplication(
            organization_id=organization_id,
            job_id=job_id,
            candidate_id=candidate_id,
            resume_id=resume_id,
        )
        db.add(application)
        db.flush()
        return application

    def get(
        self,
        db: Session,
        *,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> JobApplication:
        """Return one job application by id, enforcing organization scope."""
        application = db.get(JobApplication, application_id)
        if application is None or application.organization_id != organization_id:
            raise NotFoundError("JobApplication was not found.")
        return application

    def list_by_job(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[JobApplication]:
        """Return all job applications for a job, enforcing organization scope."""
        from app.services.job_service import JobService

        JobService().get(db, job_id=job_id, organization_id=organization_id)
        return list(
            db.scalars(
                select(JobApplication)
                .where(
                    JobApplication.job_id == job_id,
                    JobApplication.organization_id == organization_id,
                )
                .order_by(JobApplication.created_at)
            )
        )
