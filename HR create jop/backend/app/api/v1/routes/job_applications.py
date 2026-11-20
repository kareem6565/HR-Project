import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidate_pool import JobCandidateSummary
from app.api.v1.schemas.job_applications import (
    ApplicationPageResponse,
    ApplicationSummaryResponse,
    JobApplicationCreate,
    JobApplicationResponse,
    RequirementEvidenceSummary,
)
from app.api.v1.schemas.review import ReviewBundleResponse, ReviewCandidateInfo
from app.core.database import get_db
from app.models import ScreeningBatch, ScreeningBatchItem
from app.services.job_application_service import JobApplicationService
from app.services.review_service import ReviewService

router = APIRouter()


def _screening_status(
    db: Session,
    application_id: uuid.UUID,
    organization_id: uuid.UUID,
    application_state: str | None = None,
) -> str:
    item = db.scalar(
        select(ScreeningBatchItem)
        .join(ScreeningBatch, ScreeningBatch.id == ScreeningBatchItem.batch_id)
        .where(
            ScreeningBatchItem.application_id == application_id,
            ScreeningBatch.organization_id == organization_id,
        )
        .order_by(ScreeningBatchItem.created_at.desc(), ScreeningBatchItem.id.desc())
        .limit(1)
    )
    if item is None:
        return {
            "analysis_pending": "queued",
            "analyzing": "processing",
            "analysis_failed": "failed",
            "ready_for_review": "completed",
        }.get(application_state, "not_started")
    return {
        "queued": "queued",
        "running": "processing",
        "done": "completed",
        "failed": "failed",
    }.get(item.status, "not_started")


@router.post(
    "/job-applications",
    response_model=JobApplicationResponse,
    status_code=201,
)
def create_job_application(
    body: JobApplicationCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobApplicationService().create(
        db,
        organization_id=ctx.organization_id,
        job_id=uuid.UUID(body.job_id) if isinstance(body.job_id, str) else body.job_id,
        candidate_id=(
            uuid.UUID(body.candidate_id)
            if isinstance(body.candidate_id, str)
            else body.candidate_id
        ),
        resume_id=(
            uuid.UUID(body.resume_id) if isinstance(body.resume_id, str) else body.resume_id
        ),
    )


@router.get(
    "/job-applications",
    response_model=list[ApplicationSummaryResponse] | ApplicationPageResponse,
)
def list_org_applications(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    candidate_id: uuid.UUID | None = Query(default=None),
    job_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    source: str | None = Query(default=None, max_length=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    processing_status: str | None = Query(
        default=None, pattern="^(not_started|queued|processing|completed|failed)$"
    ),
    decision_status: str | None = Query(
        default=None, pattern="^(pending_review|advanced|hold|rejected)$"
    ),
    sort_by: str = Query(default="created_at", pattern="^(created_at|score)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to.")
    results = ReviewService().list_application_summaries(
        db,
        organization_id=ctx.organization_id,
        status=status,
        candidate_id=candidate_id,
        job_id=job_id,
        search=search,
        source=source,
        date_from=date_from,
        date_to=date_to,
        processing_status=processing_status,
        decision_status=decision_status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    if page is None:
        rows = results
        total = len(rows)
    else:
        rows, total = results
    summaries = []
    for row in rows:
        evaluation = row.current_evaluation
        score = (
            str(evaluation.score)
            if evaluation is not None and evaluation.score is not None
            else None
        )
        summaries.append(
            ApplicationSummaryResponse(
                id=row.application.id,
                candidate_id=row.candidate.id,
                candidate_name=row.candidate.full_name,
                candidate_email=row.candidate.email,
                candidate_phone=row.candidate.phone,
                job_id=row.job.id,
                job_title=row.job.title,
                score=score,
                group=row.group,
                status=row.application.status,
                screening_status=row.screening_status,
                decision_status=(
                    {"advance": "advanced", "reject": "rejected"}.get(
                        row.latest_decision.decision, row.latest_decision.decision
                    )
                    if row.latest_decision
                    else (
                        row.application.status
                        if row.application.status in {"advanced", "hold", "rejected"}
                        else "pending_review"
                    )
                ),
                decision_created_at=row.latest_decision.created_at if row.latest_decision else None,
                source=row.application.source,
                source_medium=row.application.source_medium,
                source_campaign=row.application.source_campaign,
                created_at=row.application.created_at,
                evidence=[
                    RequirementEvidenceSummary(
                        requirement_key=item.requirement_key,
                        evidence_type=item.evidence_type,
                        text=item.text,
                    )
                    for item in row.evidence
                ],
            )
        )
    if page is None:
        return summaries
    return ApplicationPageResponse(
        items=summaries,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/job-applications/{application_id}",
    response_model=JobApplicationResponse,
)
def get_job_application(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    application = JobApplicationService().get(
        db,
        application_id=uuid.UUID(application_id),
        organization_id=ctx.organization_id,
    )
    return {
        **JobApplicationResponse.model_validate(application).model_dump(),
        "screening_status": _screening_status(
            db, application.id, ctx.organization_id, application.status
        ),
    }


@router.get(
    "/job-applications/{application_id}/review-bundle",
    response_model=ReviewBundleResponse,
)
def get_review_bundle(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    bundle = ReviewService().get_review_bundle(
        db,
        application_id=uuid.UUID(application_id),
        organization_id=ctx.organization_id,
    )
    current = bundle.current_evaluation
    score = str(current.score) if current is not None and current.score is not None else None
    decision = bundle.latest_decision
    pool_row = JobCandidateSummary(
        candidate_id=bundle.candidate.id,
        application_id=bundle.application.id,
        full_name=bundle.candidate.full_name,
        email=bundle.candidate.email,
        phone=bundle.candidate.phone,
        status=bundle.application.status,
        score=score,
        group=bundle.group,
        decision=decision.decision if decision else None,
        decision_created_at=decision.created_at if decision else None,
    )
    candidate = ReviewCandidateInfo(
        id=bundle.candidate.id,
        name=bundle.candidate.full_name,
        email=bundle.candidate.email,
        phone=bundle.candidate.phone,
    )
    return ReviewBundleResponse(
        application={
            **JobApplicationResponse.model_validate(bundle.application).model_dump(),
            "screening_status": _screening_status(
                db,
                bundle.application.id,
                ctx.organization_id,
                bundle.application.status,
            ),
        },
        candidate=candidate,
        job=bundle.job,
        evaluations=bundle.evaluations,
        evaluation=current,
        evidence=bundle.evidence,
        pool_row=pool_row,
        decision_history=bundle.decision_history,
    )


@router.get(
    "/jobs/{job_id}/applications",
    response_model=list[JobApplicationResponse],
)
def list_job_applications(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    applications = JobApplicationService().list_by_job(
        db,
        job_id=uuid.UUID(job_id),
        organization_id=ctx.organization_id,
    )
    return [
        {
            **JobApplicationResponse.model_validate(item).model_dump(),
            "screening_status": _screening_status(db, item.id, ctx.organization_id, item.status),
        }
        for item in applications
    ]
