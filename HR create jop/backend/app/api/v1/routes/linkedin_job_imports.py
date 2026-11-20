from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.linkedin_job_imports import (
    LinkedInJobImportRequest,
    LinkedInJobImportResponse,
)
from app.core.config import settings
from app.core.database import get_db
from app.models import LinkedInJobImport
from app.services.linkedin_job_import_service import (
    LinkedInJobImportService,
    canonicalize_linkedin_job_url,
)

router = APIRouter()


def _integration_ready() -> bool:
    return bool(
        settings.apify_import_enabled
        and settings.apify_api_token
        and settings.apify_linkedin_jobs_actor_id
    )


@router.post(
    "/jobs/linkedin-imports",
    response_model=LinkedInJobImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_linkedin_job_import(
    body: LinkedInJobImportRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if not _integration_ready():
        raise HTTPException(status_code=503, detail="LinkedIn import is not enabled.")
    try:
        source_url, source_job_id = canonicalize_linkedin_job_url(str(body.source_url))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

    record = db.scalar(
        select(LinkedInJobImport).where(
            LinkedInJobImport.organization_id == ctx.organization_id,
            LinkedInJobImport.source_url == source_url,
        )
    )
    if record:
        retryable_failure = (
            record.status == "failed"
            and record.actor_run_id
            and (record.error_code == "actor_failed")
        )
        if retryable_failure:
            record.status = "queued"
            record.error_code = None
            record.finished_at = None
            record.actor_run_id = None
            await LinkedInJobImportService().start_actor(record)
            db.commit()
            db.refresh(record)
        return LinkedInJobImportService.response_payload(record)

    active_count = db.scalar(
        select(func.count(LinkedInJobImport.id)).where(
            LinkedInJobImport.organization_id == ctx.organization_id,
            LinkedInJobImport.status.in_(("queued", "running")),
        )
    )
    if active_count >= 3:
        raise HTTPException(
            status_code=429,
            detail="This organization already has three LinkedIn imports in progress.",
        )

    record = LinkedInJobImport(
        organization_id=ctx.organization_id,
        requested_by_user_id=ctx.user_id,
        source_url=source_url,
        source_job_id=source_job_id,
        actor_id=settings.apify_linkedin_jobs_actor_id,
        status="queued",
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(LinkedInJobImport).where(
                LinkedInJobImport.organization_id == ctx.organization_id,
                LinkedInJobImport.source_url == source_url,
            )
        )
        if existing is None:
            raise HTTPException(
                status_code=409, detail="Import is already being created."
            ) from None
        return LinkedInJobImportService.response_payload(existing)

    db.commit()
    db.refresh(record)
    await LinkedInJobImportService().start_actor(record)
    db.commit()
    db.refresh(record)
    return LinkedInJobImportService.response_payload(record)


@router.get("/jobs/linkedin-imports/{import_id}", response_model=LinkedInJobImportResponse)
async def get_linkedin_job_import(
    import_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if not _integration_ready():
        raise HTTPException(status_code=503, detail="LinkedIn import is not enabled.")
    record = LinkedInJobImportService.get_by_id(
        db, import_id=import_id, organization_id=ctx.organization_id
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Import was not found.")
    await LinkedInJobImportService().refresh(record)
    db.commit()
    db.refresh(record)
    return LinkedInJobImportService.response_payload(record)
