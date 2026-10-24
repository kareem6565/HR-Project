import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidate_pool import JobCandidateSummary, TalentPoolRowResponse
from app.core.database import get_db
from app.services.candidate_pool_service import CandidatePoolService
from app.services.review_service import ReviewService

def _format_score(score: Any) -> str | None:
    if score is None:
        return None
    try:
        val = Decimal(str(score))
        if val == val.to_integral():
            return str(int(val))
        return f"{float(val):.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(score)


router = APIRouter()


@router.get(
    "/jobs/{job_id}/candidates",
    response_model=list[JobCandidateSummary],
)
def list_job_candidates(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    min_score: Decimal | None = Query(default=None),
    max_score: Decimal | None = Query(default=None),
    search: str | None = Query(default=None),
    group: str | None = Query(default=None),
):
    entries = CandidatePoolService().list_ranked_candidates(
        db,
        job_id=uuid.UUID(job_id),
        organization_id=ctx.organization_id,
        status=status,
        decision=decision,
        min_score=min_score,
        max_score=max_score,
        search=search,
        group=group,
    )

    summaries = []
    for entry in entries:
        evaluation = entry.current_evaluation
        score = _format_score(evaluation.score if evaluation is not None else None)
        decision = entry.latest_decision
        summaries.append(
            JobCandidateSummary(
                candidate_id=entry.candidate.id,
                application_id=entry.application.id,
                full_name=entry.candidate.full_name,
                email=entry.candidate.email,
                phone=entry.candidate.phone,
                status=entry.application.status,
                score=score,
                group=entry.group,
                decision=decision.decision if decision else None,
                decision_created_at=decision.created_at if decision else None,
            )
        )

    return summaries


@router.get(
    "/talent-pool",
    response_model=list[TalentPoolRowResponse],
)
def list_talent_pool(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    rows = ReviewService().list_talent_pool(
        db,
        organization_id=ctx.organization_id,
    )

    talent_pool = []
    for row in rows:
        evaluation = row.current_evaluation
        score = _format_score(evaluation.score if evaluation is not None else None)
        decision = row.latest_decision
        talent_pool.append(
            TalentPoolRowResponse(
                candidate_id=row.candidate.id,
                application_id=row.application.id,
                job_id=row.job.id,
                job_title=row.job.title,
                full_name=row.candidate.full_name,
                email=row.candidate.email,
                phone=row.candidate.phone,
                status=row.application.status,
                score=score,
                group=row.group,
                skills=row.skills,
                decision=decision.decision if decision else None,
                decision_created_at=decision.created_at if decision else None,
            )
        )

    return talent_pool
