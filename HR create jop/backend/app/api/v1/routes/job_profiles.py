import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.job_profiles import JobProfileCreate, JobProfileResponse
from app.core.database import get_db
from app.services.job_profile_service import JobProfileService

router = APIRouter()


@router.post(
    "/jobs/{job_id}/profiles",
    response_model=JobProfileResponse,
    status_code=201,
)
def create_job_profile(
    job_id: str,
    body: JobProfileCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    provenance = None
    raw_input_snapshot = dict(body.raw_input_snapshot or {})
    if body.source_metadata is not None:
        if not body.source_metadata.review_confirmed:
            from app.services.errors import ValidationError

            raise ValidationError("Confirm that you reviewed the source before saving it.")
        if not body.source_original_listing_text or not body.source_original_listing_text.strip():
            from app.services.errors import ValidationError

            raise ValidationError("The original listing text is required with source details.")
        raw_input_snapshot["original_listing_text"] = body.source_original_listing_text
        provenance = {
            "source": {
                **body.source_metadata.model_dump(mode="json", exclude={"review_confirmed"}),
                "reviewed_at": datetime.now(UTC).isoformat(),
                "reviewed_by_user_id": str(ctx.user_id),
                "availability_checked_by_hera": False,
            },
            "field_origins": body.field_origins or {},
        }
    return JobProfileService().create_version(
        db,
        job_id=uuid.UUID(job_id),
        status=body.status,
        source=body.source,
        profile_data=body.profile_data,
        raw_input_snapshot=raw_input_snapshot or None,
        provenance=provenance,
        organization_id=ctx.organization_id,
    )


@router.get("/jobs/{job_id}/profiles", response_model=list[JobProfileResponse])
def list_job_profiles(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobProfileService().list_versions(
        db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id
    )


@router.get("/job-profiles/{profile_id}", response_model=JobProfileResponse)
def get_job_profile(
    profile_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobProfileService().get_version(
        db, profile_id=uuid.UUID(profile_id), organization_id=ctx.organization_id
    )


@router.post("/job-profiles/{profile_id}/approve", response_model=JobProfileResponse)
def approve_job_profile(
    profile_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.job_service import JobService

    profile = JobProfileService().approve(
        db,
        profile_id=uuid.UUID(profile_id),
        approved_by_user_id=ctx.user_id,
        organization_id=ctx.organization_id,
    )
    job = JobService().get(db, job_id=profile.job_id, organization_id=ctx.organization_id)
    if job.status == "awaiting_profile_review":
        job.status = "active"
    return profile
