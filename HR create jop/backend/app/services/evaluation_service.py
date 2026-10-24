from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CandidateEvaluation,
    CandidateProfile,
    HRDecision,
    JobApplication,
    JobProfile,
    MatchEvidence,
)
from app.services.errors import NotFoundError, ValidationError, VersionConflictError

VALID_STATUSES = frozenset({"queued", "running", "completed", "failed", "superseded"})
VALID_EVIDENCE_TYPES = frozenset({"matched", "missing", "partial"})


class EvaluationService:
    """Deterministic creation and retrieval for candidate evaluations and evidence."""

    def create_version(
        self,
        db: Session,
        *,
        job_application_id: uuid.UUID,
        job_profile_id: uuid.UUID,
        candidate_profile_id: uuid.UUID,
        status: str,
        score: Decimal | None = None,
        recommendation: str | None = None,
        explanation: dict[str, Any] | None = None,
        score_breakdown: dict[str, Any] | None = None,
        scoring_version: str | None = None,
        evidence_engine_version: str | None = "2.0",
        provenance: dict[str, Any] | None = None,
        organization_id: uuid.UUID | None = None,
        make_current: bool = True,
    ) -> CandidateEvaluation:
        """Create a versioned evaluation after checking recruitment context consistency."""
        if status not in VALID_STATUSES:
            raise ValidationError(f"Invalid candidate evaluation status: {status!r}.")
        application = self._get_application(
            db,
            job_application_id=job_application_id,
            organization_id=organization_id,
        )
        job_profile = self._get_job_profile(
            db, job_profile_id=job_profile_id, organization_id=application.organization_id
        )
        candidate_profile = self._get_candidate_profile(
            db,
            candidate_profile_id=candidate_profile_id,
            organization_id=application.organization_id,
        )
        self._validate_context(
            application=application,
            job_profile=job_profile,
            candidate_profile=candidate_profile,
        )

        version_number = self._next_version_number(db, job_application_id=job_application_id)
        if make_current:
            self._clear_current(db, job_application_id=job_application_id)

        evaluation = CandidateEvaluation(
            job_application_id=job_application_id,
            job_profile_id=job_profile_id,
            candidate_profile_id=candidate_profile_id,
            version_number=version_number,
            status=status,
            score=score,
            recommendation=recommendation,
            explanation=explanation,
            score_breakdown=score_breakdown,
            scoring_version=scoring_version,
            evidence_engine_version=evidence_engine_version,
            provenance=provenance,
            is_current=make_current,
        )
        db.add(evaluation)
        self._flush_version(db)
        return evaluation

    def get_version(
        self,
        db: Session,
        *,
        evaluation_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> CandidateEvaluation:
        """Return one candidate evaluation by id."""
        evaluation = db.get(CandidateEvaluation, evaluation_id)
        if evaluation is None:
            raise NotFoundError("CandidateEvaluation was not found.")
        if (
            organization_id is not None
            and evaluation.job_application.organization_id != organization_id
        ):
            raise NotFoundError("CandidateEvaluation was not found.")
        return evaluation

    def list_versions(
        self,
        db: Session,
        *,
        job_application_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> list[CandidateEvaluation]:
        """Return all evaluations for an application ordered by version number."""
        self._get_application(
            db,
            job_application_id=job_application_id,
            organization_id=organization_id,
        )
        return list(
            db.scalars(
                select(CandidateEvaluation)
                .where(CandidateEvaluation.job_application_id == job_application_id)
                .order_by(CandidateEvaluation.version_number)
            )
        )

    def get_current_or_latest(
        self,
        db: Session,
        *,
        job_application_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> CandidateEvaluation | None:
        """Return the current evaluation, falling back to the latest version."""
        versions = self.list_versions(
            db,
            job_application_id=job_application_id,
            organization_id=organization_id,
        )
        current_versions = [evaluation for evaluation in versions if evaluation.is_current]
        if current_versions:
            return current_versions[-1]
        return versions[-1] if versions else None

    def add_match_evidence(
        self,
        db: Session,
        *,
        candidate_evaluation_id: uuid.UUID,
        evidence_type: str,
        requirement_ref: dict[str, Any] | None = None,
        candidate_evidence: dict[str, Any] | None = None,
        strength: str | None = None,
        provenance: dict[str, Any] | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> MatchEvidence:
        """Persist caller-supplied match evidence for an existing evaluation."""
        if evidence_type not in VALID_EVIDENCE_TYPES:
            raise ValidationError(f"Invalid match evidence type: {evidence_type!r}.")
        self.get_version(
            db,
            evaluation_id=candidate_evaluation_id,
            organization_id=organization_id,
        )
        evidence = MatchEvidence(
            candidate_evaluation_id=candidate_evaluation_id,
            evidence_type=evidence_type,
            requirement_ref=requirement_ref,
            candidate_evidence=candidate_evidence,
            strength=strength,
            provenance=provenance,
        )
        db.add(evidence)
        db.flush()
        return evidence

    def _get_application(
        self,
        db: Session,
        *,
        job_application_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> JobApplication:
        application = db.get(JobApplication, job_application_id)
        if application is None:
            raise NotFoundError("JobApplication was not found.")
        if organization_id is not None and application.organization_id != organization_id:
            raise NotFoundError("JobApplication was not found.")
        return application

    def _get_job_profile(
        self, db: Session, *, job_profile_id: uuid.UUID, organization_id: uuid.UUID | None = None
    ) -> JobProfile:
        job_profile = db.get(JobProfile, job_profile_id)
        if job_profile is None:
            raise NotFoundError("JobProfile was not found.")
        if organization_id is not None and job_profile.job.organization_id != organization_id:
            raise NotFoundError("JobProfile was not found.")
        return job_profile

    def _get_candidate_profile(
        self,
        db: Session,
        *,
        candidate_profile_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> CandidateProfile:
        candidate_profile = db.get(CandidateProfile, candidate_profile_id)
        if candidate_profile is None:
            raise NotFoundError("CandidateProfile was not found.")
        if (
            organization_id is not None
            and candidate_profile.resume.candidate.organization_id != organization_id
        ):
            raise NotFoundError("CandidateProfile was not found.")
        return candidate_profile

    def _validate_context(
        self,
        *,
        application: JobApplication,
        job_profile: JobProfile,
        candidate_profile: CandidateProfile,
    ) -> None:
        if job_profile.job_id != application.job_id:
            raise ValidationError("JobProfile must belong to the JobApplication job.")
        if candidate_profile.resume_id != application.resume_id:
            raise ValidationError("CandidateProfile must belong to the JobApplication resume.")

    def _next_version_number(self, db: Session, *, job_application_id: uuid.UUID) -> int:
        current_max = db.scalar(
            select(func.max(CandidateEvaluation.version_number)).where(
                CandidateEvaluation.job_application_id == job_application_id
            )
        )
        return (current_max or 0) + 1

    def _clear_current(self, db: Session, *, job_application_id: uuid.UUID) -> None:
        db.execute(
            update(CandidateEvaluation)
            .where(
                CandidateEvaluation.job_application_id == job_application_id,
                CandidateEvaluation.is_current.is_(True),
            )
            .values(is_current=False)
        )

    def _flush_version(self, db: Session) -> None:
        try:
            db.flush()
        except IntegrityError as error:
            raise VersionConflictError(
                "CandidateEvaluation version could not be created."
            ) from error

    def has_hr_decision(self, db: Session, *, evaluation_id: uuid.UUID) -> bool:
        """Return whether an evaluation already has an HR decision reference."""
        decision_id = db.scalar(
            select(HRDecision.id).where(HRDecision.candidate_evaluation_id == evaluation_id)
        )
        return decision_id is not None
