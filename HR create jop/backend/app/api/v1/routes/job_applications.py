import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidate_pool import JobCandidateSummary
from app.api.v1.schemas.job_applications import (
    ApplicationSummaryResponse,
    JobApplicationCreate,
    JobApplicationResponse,
    RequirementEvidenceSummary,
)
from app.api.v1.schemas.review import ReviewBundleResponse, ReviewCandidateInfo
from app.core.database import get_db
from app.services.job_application_service import JobApplicationService
from app.services.review_service import ReviewService

router = APIRouter()


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
    response_model=list[ApplicationSummaryResponse],
)
def list_org_applications(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    candidate_id: uuid.UUID | None = Query(default=None),
):
    rows = ReviewService().list_application_summaries(
        db,
        organization_id=ctx.organization_id,
        status=status,
        candidate_id=candidate_id,
    )
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
                job_id=row.job.id,
                job_title=row.job.title,
                score=score,
                group=row.group,
                status=row.application.status,
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
    return summaries


@router.get(
    "/job-applications/{application_id}",
    response_model=JobApplicationResponse,
)
def get_job_application(
    application_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobApplicationService().get(
        db,
        application_id=uuid.UUID(application_id),
        organization_id=ctx.organization_id,
    )


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
        application=bundle.application,
        candidate=candidate,
        job=bundle.job,
        evaluations=bundle.evaluations,
        evaluation=current,
        evidence=bundle.evidence,
        pool_row=pool_row,
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
    return JobApplicationService().list_by_job(
        db,
        job_id=uuid.UUID(job_id),
        organization_id=ctx.organization_id,
    )
