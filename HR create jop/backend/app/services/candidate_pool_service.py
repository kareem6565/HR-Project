from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candidate, CandidateEvaluation, HRDecision, JobApplication
from app.services.errors import ValidationError
from app.services.job_service import JobService

# Deterministic, non-configurable grouping bands (Phase 4.5 decision #2).
MUST_REVIEW_MIN = 70
CONSIDER_MIN = 40

GROUP_MUST_REVIEW = "must_review"
GROUP_CONSIDER = "consider"
GROUP_LOWER_PRIORITY = "lower_priority"

VALID_GROUPS = frozenset({GROUP_MUST_REVIEW, GROUP_CONSIDER, GROUP_LOWER_PRIORITY})

VALID_APPLICATION_STATUSES = frozenset(
    {
        "created",
        "analysis_pending",
        "analyzing",
        "analysis_failed",
        "ready_for_review",
        "hold",
        "advanced",
        "rejected",
        "archived",
    }
)

VALID_DECISION_FILTERS = frozenset({"advance", "reject", "hold"})


@dataclass(frozen=True)
class CandidatePoolEntry:
    """One application/candidate in a job's ranked candidate pool."""

    application: JobApplication
    candidate: Candidate
    current_evaluation: CandidateEvaluation | None
    latest_decision: HRDecision | None
    group: str


def assign_group(score: Decimal | None) -> str:
    """Map a score to its deterministic grouping label.

    Candidates without a score (no completed current evaluation) are treated as
    ``lower_priority`` so they are never hidden by grouping.
    """
    if score is None:
        return GROUP_LOWER_PRIORITY
    if score >= MUST_REVIEW_MIN:
        return GROUP_MUST_REVIEW
    if score >= CONSIDER_MIN:
        return GROUP_CONSIDER
    return GROUP_LOWER_PRIORITY


class CandidatePoolService:
    """Read-only, job-scoped candidate ranking, grouping, filtering, and search.

    Keyed off a Job's application pool only (no org-wide candidate listing).
    Reuses the persisted deterministic score; never recomputes or changes
    scores and never touches the AI or scoring services.
    """

    def list_ranked_candidates(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str | None = None,
        decision: str | None = None,
        min_score: Decimal | None = None,
        max_score: Decimal | None = None,
        search: str | None = None,
        group: str | None = None,
    ) -> list[CandidatePoolEntry]:
        """Return candidates for a job, ranked by current score descending.

        Organization scope is enforced via the owning Job (cross-org access
        raises a typed ``ValidationError`` mapped to 422). Only each
        application's current evaluation is considered (``is_current=True``),
        avoiding any load of version history and any N+1. Decisions are
        left-joined so candidates without a decision are never hidden.
        """
        self._validate_filters(
            status=status,
            decision=decision,
            min_score=min_score,
            max_score=max_score,
            group=group,
        )

        JobService().get(db, job_id=job_id, organization_id=organization_id)

        latest_decision_id = (
            select(HRDecision.id)
            .where(HRDecision.job_application_id == JobApplication.id)
            .order_by(HRDecision.created_at.desc())
            .limit(1)
            .correlate(JobApplication)
            .scalar_subquery()
        )

        query = (
            select(JobApplication, Candidate, CandidateEvaluation, HRDecision)
            .join(Candidate, Candidate.id == JobApplication.candidate_id)
            .outerjoin(
                CandidateEvaluation,
                (CandidateEvaluation.job_application_id == JobApplication.id)
                & CandidateEvaluation.is_current.is_(True),
            )
            .outerjoin(HRDecision, HRDecision.id == latest_decision_id)
            .where(JobApplication.job_id == job_id)
        )

        query = self._apply_filters(
            query,
            status=status,
            decision=decision,
            min_score=min_score,
            max_score=max_score,
            search=search,
        )

        rows = db.execute(query).all()

        entries = [
            CandidatePoolEntry(
                application=application,
                candidate=candidate,
                current_evaluation=evaluation,
                latest_decision=decision,
                group=assign_group(evaluation.score if evaluation else None),
            )
            for application, candidate, evaluation, decision in rows
        ]

        entries.sort(
            key=lambda entry: (
                entry.current_evaluation is None or entry.current_evaluation.score is None,
                -(entry.current_evaluation.score or 0) if entry.current_evaluation else 0,
            )
        )

        if group is not None:
            entries = [entry for entry in entries if entry.group == group]

        return entries

    def _apply_filters(
        self,
        query,
        *,
        status: str | None,
        decision: str | None,
        min_score: Decimal | None,
        max_score: Decimal | None,
        search: str | None,
    ):
        if status is not None:
            query = query.where(JobApplication.status == status)
        if decision is not None:
            query = query.where(HRDecision.id.is_not(None))
            query = query.where(HRDecision.decision == decision)
        if min_score is not None:
            query = query.where(CandidateEvaluation.score >= min_score)
        if max_score is not None:
            query = query.where(CandidateEvaluation.score <= max_score)
        if search:
            like = f"%{self._escape_like(search)}%"
            query = query.where(Candidate.full_name.ilike(like) | Candidate.email.ilike(like))
        return query

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _validate_filters(
        *,
        status: str | None,
        decision: str | None,
        min_score: Decimal | None,
        max_score: Decimal | None,
        group: str | None,
    ) -> None:
        if status is not None and status not in VALID_APPLICATION_STATUSES:
            raise ValidationError(f"Invalid application status filter: {status!r}.")
        if decision is not None and decision not in VALID_DECISION_FILTERS:
            raise ValidationError(f"Invalid decision filter: {decision!r}.")
        if group is not None and group not in VALID_GROUPS:
            raise ValidationError(f"Invalid group filter: {group!r}.")
        if min_score is not None and not 0 <= min_score <= 100:
            raise ValidationError("min_score must be between 0 and 100.")
        if max_score is not None and not 0 <= max_score <= 100:
            raise ValidationError("max_score must be between 0 and 100.")
        if min_score is not None and max_score is not None and min_score > max_score:
            raise ValidationError("min_score cannot exceed max_score.")
