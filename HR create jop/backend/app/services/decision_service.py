"""Deterministic human-decision application service (Phase 3.7).

Enables HR to explicitly record an HRDecision after reviewing an AI-assisted
CandidateEvaluation. This is a purely deterministic, service-layer operation and
is the ONLY sanctioned way to create an HR decision: AI workflows must never
create, modify, or finalize an HRDecision, and the final decision always belongs
to the HR professional.

The service validates the referenced JobApplication, the acting HR User, and an
optional CandidateEvaluation (which must belong to the same JobApplication and,
when an organization is supplied, the same organization). It enforces the
authoritative decision vocabulary from the ``hr_decisions`` CHECK constraint and
preserves append-only history: every call inserts a new row and never mutates
prior decisions, the CandidateEvaluation, or any JobProfile/CandidateProfile.

Recording a decision also mirrors it into the application's pipeline status so
the org-wide talent pool (hold/advanced candidates) reflects real HR actions:
``advance`` → ``advanced``, ``hold`` → ``hold``, ``reject`` → ``rejected``.

This service never commits (the caller owns the transaction), never calls an AI
provider or workflow, never computes a score or recommendation, and records no
workflow/AI traces.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CandidateEvaluation, HRDecision, JobApplication, User
from app.services.audit_service import AuditService
from app.services.errors import ConflictError, NotFoundError, ValidationError

VALID_DECISIONS = frozenset({"advance", "reject", "hold"})

# The pipeline status each HR decision moves the application into. These values
# are the authoritative ``job_applications.status`` vocabulary.
DECISION_TO_STATUS = {
    "advance": "advanced",
    "hold": "hold",
    "reject": "rejected",
}


def _validate_decision(decision: str) -> None:
    """Validate a decision against the authoritative DB constraint vocabulary."""
    if decision not in VALID_DECISIONS:
        raise ValidationError(f"Invalid HR decision: {decision!r}.")


class DecisionService:
    """Deterministic creation and retrieval of HR decisions."""

    def create(
        self,
        db: Session,
        *,
        job_application_id: uuid.UUID,
        user_id: uuid.UUID,
        decision: str,
        candidate_evaluation_id: uuid.UUID | None = None,
        expected_evaluation_id: uuid.UUID | None = None,
        reason: str | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> HRDecision:
        """Record a new append-only HR decision for a JobApplication."""
        _validate_decision(decision)

        # 1. Lock the application row for update to prevent concurrent overwrites
        application = self._get_application_for_update(
            db,
            job_application_id=job_application_id,
            organization_id=organization_id,
        )
        self._get_user(
            db,
            user_id=user_id,
            expected_organization_id=organization_id,
            application=application,
        )

        # 2. Resolve and validate evaluation, including freshness guarantees
        evaluation = self._get_evaluation(
            db,
            candidate_evaluation_id=candidate_evaluation_id,
            expected_evaluation_id=expected_evaluation_id,
            application=application,
            organization_id=organization_id,
        )

        resolved_eval_id = evaluation.id if evaluation is not None else None

        # 3. Check for idempotent retry / repeated submission
        latest_decision = db.scalars(
            select(HRDecision)
            .where(HRDecision.job_application_id == application.id)
            .order_by(HRDecision.created_at.desc(), HRDecision.id.desc())
            .limit(1)
        ).first()

        if (
            latest_decision is not None
            and latest_decision.decision == decision
            and latest_decision.user_id == user_id
            and latest_decision.candidate_evaluation_id == resolved_eval_id
            and (latest_decision.reason or None) == (reason or None)
        ):
            # Idempotent replay: return existing decision without duplicate record or audit log
            return latest_decision

        prev_status = application.status
        new_status = DECISION_TO_STATUS[decision]

        decision_row = HRDecision(
            job_application_id=application.id,
            user_id=user_id,
            candidate_evaluation_id=resolved_eval_id,
            decision=decision,
            reason=reason,
        )
        db.add(decision_row)

        # Mirror the decision into the application's pipeline status
        application.status = new_status

        # Write audit event in the exact same transaction before flush
        AuditService().log_event(
            db,
            action="hr_decision.created",
            entity_type="job_application",
            organization_id=application.organization_id,
            actor_user_id=user_id,
            entity_id=application.id,
            metadata={
                "decision": decision,
                "decision_id": str(decision_row.id),
                "candidate_evaluation_id": str(resolved_eval_id) if resolved_eval_id else None,
                "evaluation_version": evaluation.version_number if evaluation else None,
                "previous_status": prev_status,
                "new_status": new_status,
            },
            flush=False,
        )

        # If an application is rejected or put on hold after an interview has been scheduled,
        # apply documented transition policy: cancel scheduled interviews to prevent contradictory state.
        if decision in ("hold", "reject"):
            from app.models.interview import Interview

            active_interviews = list(
                db.scalars(
                    select(Interview)
                    .where(
                        Interview.job_application_id == application.id,
                        Interview.status == "scheduled",
                    )
                )
            )
            for intv in active_interviews:
                intv.status = "cancelled"
                AuditService().log_event(
                    db,
                    action="interview.cancelled_by_decision",
                    entity_type="interview",
                    organization_id=application.organization_id,
                    actor_user_id=user_id,
                    entity_id=intv.id,
                    metadata={
                        "reason": f"Application decision changed to {decision}",
                        "decision": decision,
                    },
                    flush=False,
                )

        db.flush()
        return decision_row

    def _get_application_for_update(
        self,
        db: Session,
        *,
        job_application_id: uuid.UUID,
        organization_id: uuid.UUID | None,
    ) -> JobApplication:
        stmt = (
            select(JobApplication)
            .where(JobApplication.id == job_application_id)
            .with_for_update()
        )
        application = db.scalars(stmt).first()
        if application is None:
            raise NotFoundError("JobApplication was not found.")
        if organization_id is not None and application.organization_id != organization_id:
            raise NotFoundError("JobApplication was not found.")
        return application

    def _get_application(
        self,
        db: Session,
        *,
        job_application_id: uuid.UUID,
        organization_id: uuid.UUID | None,
    ) -> JobApplication:
        return self._get_application_for_update(
            db, job_application_id=job_application_id, organization_id=organization_id
        )

    def _get_user(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        expected_organization_id: uuid.UUID | None,
        application: JobApplication,
    ) -> User:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User was not found.")
        if user.organization_id != application.organization_id:
            raise ValidationError("User must belong to the same organization as the JobApplication.")
        if (
            expected_organization_id is not None
            and user.organization_id != expected_organization_id
        ):
            raise ValidationError("User must belong to the expected organization.")
        return user

    def _get_evaluation(
        self,
        db: Session,
        *,
        candidate_evaluation_id: uuid.UUID | None,
        expected_evaluation_id: uuid.UUID | None,
        application: JobApplication,
        organization_id: uuid.UUID | None,
    ) -> CandidateEvaluation | None:
        if candidate_evaluation_id and expected_evaluation_id:
            if candidate_evaluation_id != expected_evaluation_id:
                raise ConflictError("candidate_evaluation_id and expected_evaluation_id must match.")

        target_id = expected_evaluation_id or candidate_evaluation_id
        if target_id is None:
            return None

        evaluation = db.get(CandidateEvaluation, target_id)
        if evaluation is None:
            raise NotFoundError("CandidateEvaluation was not found.")
        if evaluation.job_application.organization_id != application.organization_id:
            raise NotFoundError("CandidateEvaluation was not found.")
        if evaluation.job_application_id != application.id:
            raise ValidationError("CandidateEvaluation must belong to the JobApplication.")
        if organization_id is not None and application.organization_id != organization_id:
            raise NotFoundError("CandidateEvaluation was not found.")

        # Freshness verification when expected_evaluation_id is specified
        if expected_evaluation_id is not None:
            if not evaluation.is_current or evaluation.status == "superseded":
                raise ConflictError("The referenced evaluation is stale and has been superseded.")

            newer_count = db.scalar(
                select(func.count())
                .select_from(CandidateEvaluation)
                .where(
                    CandidateEvaluation.job_application_id == application.id,
                    CandidateEvaluation.version_number > evaluation.version_number,
                )
            )
            if newer_count and newer_count > 0:
                raise ConflictError("The referenced evaluation is stale and has been superseded.")

        return evaluation
