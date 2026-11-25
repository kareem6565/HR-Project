import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context, require_roles
from app.api.v1.schemas.candidates import (
    CandidateCreate,
    CandidateListResponse,
    CandidateResponse,
    CandidateUpdate,
)
from app.api.v1.schemas.resumes import ResumeResponse
from app.core.config import settings
from app.core.database import get_db
from app.models import Candidate, Organization
from app.services.candidate_privacy_service import CandidatePrivacyService
from app.services.candidate_service import CandidateService
from app.services.errors import NotFoundError
from app.services.resume_service import ResumeService

router = APIRouter()


class LegalHoldUpdate(BaseModel):
    enabled: bool


class RetentionPolicyUpdate(BaseModel):
    rejected_retention_months: int = Field(ge=1, le=120)
    talent_pool_retention_months: int = Field(ge=1, le=120)


@router.patch("/candidates/{candidate_id}/legal-hold")
def set_candidate_legal_hold(
    candidate_id: uuid.UUID,
    body: LegalHoldUpdate,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    candidate = db.scalar(
        select(Candidate).where(
            Candidate.id == candidate_id, Candidate.organization_id == ctx.organization_id
        )
    )
    if candidate is None:
        raise NotFoundError("Candidate was not found.")
    candidate.legal_hold = body.enabled
    db.flush()
    return {"candidate_id": str(candidate.id), "legal_hold": candidate.legal_hold}


@router.post("/candidates/{candidate_id}/erase")
def erase_candidate_data(
    candidate_id: uuid.UUID,
    dry_run: bool = Query(default=False),
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    return CandidatePrivacyService().erase_candidate(
        db,
        candidate_id=candidate_id,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        dry_run=dry_run,
    )


@router.get("/organization/retention-policy")
def get_retention_policy(
    ctx: RequestContext = Depends(require_roles("admin")), db: Session = Depends(get_db)
):
    organization = db.get(Organization, ctx.organization_id)
    if organization is None:
        raise NotFoundError("Organization was not found.")
    return {
        "rejected_retention_months": organization.rejected_retention_months,
        "talent_pool_retention_months": organization.talent_pool_retention_months,
        "retention_enabled": settings.retention_enabled,
    }


@router.patch("/organization/retention-policy")
def update_retention_policy(
    body: RetentionPolicyUpdate,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    organization = db.get(Organization, ctx.organization_id)
    if organization is None:
        raise NotFoundError("Organization was not found.")
    organization.rejected_retention_months = body.rejected_retention_months
    organization.talent_pool_retention_months = body.talent_pool_retention_months
    db.flush()
    return {
        "rejected_retention_months": organization.rejected_retention_months,
        "talent_pool_retention_months": organization.talent_pool_retention_months,
        "retention_enabled": settings.retention_enabled,
    }


@router.post("/candidates", response_model=CandidateResponse, status_code=201)
def create_candidate(
    body: CandidateCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return CandidateService().create(
        db,
        organization_id=ctx.organization_id,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
    )


@router.get("/candidates", response_model=list[CandidateListResponse])
def list_candidates(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    return CandidateService().list(
        db,
        organization_id=ctx.organization_id,
        search=search,
        status=status,
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return CandidateService().get(
        db, candidate_id=uuid.UUID(candidate_id), organization_id=ctx.organization_id
    )


@router.get("/candidates/{candidate_id}/resumes", response_model=list[ResumeResponse])
def list_candidate_resumes(
    candidate_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return ResumeService().list_for_candidate(
        db, candidate_id=uuid.UUID(candidate_id), organization_id=ctx.organization_id
    )


@router.patch("/candidates/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: str,
    body: CandidateUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return CandidateService().update(
        db,
        candidate_id=uuid.UUID(candidate_id),
        organization_id=ctx.organization_id,
        email=body.email,
        phone=body.phone,
    )


@router.post("/candidates/{candidate_id}/archive", response_model=CandidateResponse)
def archive_candidate(
    candidate_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return CandidateService().archive(
        db, candidate_id=uuid.UUID(candidate_id), organization_id=ctx.organization_id
    )
