import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidates import (
    CandidateCreate,
    CandidateListResponse,
    CandidateResponse,
    CandidateUpdate,
)
from app.api.v1.schemas.resumes import ResumeResponse
from app.core.database import get_db
from app.services.candidate_service import CandidateService
from app.services.resume_service import ResumeService

router = APIRouter()


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
