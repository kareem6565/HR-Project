from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.sourcing import SourcingSearchRequest, SourcingSearchResponse
from app.core.config import settings
from app.core.database import get_db
from app.models import Job, SourcingSearch
from app.services.sourcing_service import (
    SourcingSearchService,
    get_sourcing_provider,
)

router = APIRouter()


def _sourcing_ready() -> bool:
    return bool(
        settings.apify_sourcing_enabled
        and settings.apify_api_token
        and settings.apify_sourcing_actor_id
    )


@router.post(
    "/sourcing/searches",
    response_model=SourcingSearchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_sourcing_search(
    body: SourcingSearchRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if not _sourcing_ready():
        raise HTTPException(status_code=503, detail="LinkedIn sourcing is not enabled.")

    query_text = body.query_text.strip()
    job = None
    if body.job_id is not None:
        job = db.scalar(
            select(Job).where(Job.id == body.job_id, Job.organization_id == ctx.organization_id)
        )
        if job is None:
            raise HTTPException(status_code=404, detail="Job was not found.")
        if not query_text:
            fallback = job.description_text or job.raw_description or ""
            query_text = f"{job.title} {fallback}".strip()[:2000]

    active_count = db.scalar(
        select(func.count(SourcingSearch.id)).where(
            SourcingSearch.organization_id == ctx.organization_id,
            SourcingSearch.status.in_(("queued", "running")),
        )
    )
    if active_count >= 3:
        raise HTTPException(
            status_code=429,
            detail="This organization already has three sourcing searches in progress.",
        )

    provider = get_sourcing_provider()
    search = SourcingSearch(
        organization_id=ctx.organization_id,
        requested_by_user_id=ctx.user_id,
        job_id=job.id if job else None,
        query_text=query_text,
        provider=provider.name,
        actor_id=settings.apify_sourcing_actor_id,
        status="queued",
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    await provider.start(search)
    db.commit()
    db.refresh(search)
    return SourcingSearchService.response_payload(search)


@router.get("/sourcing/searches/{search_id}", response_model=SourcingSearchResponse)
async def get_sourcing_search(
    search_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if not _sourcing_ready():
        raise HTTPException(status_code=503, detail="LinkedIn sourcing is not enabled.")
    search = SourcingSearchService.get_by_id(
        db, search_id=search_id, organization_id=ctx.organization_id
    )
    if search is None:
        raise HTTPException(status_code=404, detail="Sourcing search was not found.")
    await get_sourcing_provider().refresh(search, db)
    db.commit()
    db.refresh(search)
    return SourcingSearchService.response_payload(search)
