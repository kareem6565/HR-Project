import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidate_profiles import CandidateProfileCreate, CandidateProfileResponse
from app.core.database import get_db
from app.services.candidate_profile_service import CandidateProfileService

router = APIRouter()


@router.post(
    "/resumes/{resume_id}/profiles",
    response_model=CandidateProfileResponse,
    status_code=201,
)
def create_candidate_profile(
    resume_id: str,
    body: CandidateProfileCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return CandidateProfileService().create_version(
        db,
        resume_id=uuid.UUID(resume_id),
        status=body.status,
        source=body.source,
        profile_data=body.profile_data,
        organization_id=ctx.organization_id,
    )


@router.get(
    "/resumes/{resume_id}/profiles",
    response_model=list[CandidateProfileResponse],
)
def list_candidate_profiles(
    resume_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return CandidateProfileService().list_versions(
        db, resume_id=uuid.UUID(resume_id), organization_id=ctx.organization_id
    )


@router.get(
    "/candidate-profiles/{profile_id}",
    response_model=CandidateProfileResponse,
)
def get_candidate_profile(
    profile_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return CandidateProfileService().get_version(
        db, profile_id=uuid.UUID(profile_id), organization_id=ctx.organization_id
    )
