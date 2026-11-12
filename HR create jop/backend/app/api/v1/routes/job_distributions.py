from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.job_distributions import (
    DistributionPostResponse,
    JobDistributionAnalyticsResponse,
    JobDistributionCreate,
    JobDistributionResponse,
    JobDistributionShare,
    JobDistributionUpdate,
)
from app.core.database import get_db
from app.models import Job, JobDistribution, JobProfile
from app.services.errors import NotFoundError
from app.services.job_distribution_service import JobDistributionService

router = APIRouter()
service = JobDistributionService()


def _company_name(db: Session, job: Job) -> str | None:
    if not job.published_job_profile_id:
        return job.organization.name
    profile = db.get(JobProfile, job.published_job_profile_id)
    provenance = (profile.provenance or {}) if profile else {}
    source = provenance.get("source") or {}
    return (
        source.get("company_name")
        or provenance.get("linkedin_import", {}).get("company_name")
        or job.organization.name
    )


@router.get("/jobs/{job_id}/distributions", response_model=list[JobDistributionResponse])
def list_job_distributions(
    job_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return service.list_for_job(db, job_id=job_id, organization_id=ctx.organization_id)


@router.post(
    "/jobs/{job_id}/distributions", response_model=JobDistributionResponse, status_code=201
)
def create_job_distribution(
    job_id: uuid.UUID,
    body: JobDistributionCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return service.create(
        db,
        job_id=job_id,
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        body=body,
    )


@router.post(
    "/job-distributions/{distribution_id}/generate",
    response_model=DistributionPostResponse,
)
def generate_distribution_post(
    distribution_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    item = db.get(JobDistribution, distribution_id)
    if item is None or item.organization_id != ctx.organization_id:
        raise NotFoundError("Distribution was not found.")
    job = db.get(Job, item.job_id)
    generated = service.generate_post(
        db,
        distribution_id=distribution_id,
        organization_id=ctx.organization_id,
        company_name=_company_name(db, job),
    )
    return DistributionPostResponse(post_text=generated.post_text, ai_generated=True)


@router.patch("/job-distributions/{distribution_id}", response_model=JobDistributionResponse)
def update_job_distribution(
    distribution_id: uuid.UUID,
    body: JobDistributionUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return service.update(
        db,
        distribution_id=distribution_id,
        organization_id=ctx.organization_id,
        body=body,
    )


@router.post(
    "/job-distributions/{distribution_id}/mark-shared", response_model=JobDistributionResponse
)
def mark_job_distribution_shared(
    distribution_id: uuid.UUID,
    body: JobDistributionShare,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return service.mark_shared(
        db,
        distribution_id=distribution_id,
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        external_post_url=str(body.external_post_url) if body.external_post_url else None,
    )


@router.get("/distribution-analytics", response_model=JobDistributionAnalyticsResponse)
def get_distribution_analytics(
    range_days: Annotated[Literal["30", "90"], Query()] = "30",
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return service.analytics(db, organization_id=ctx.organization_id, range_days=int(range_days))
