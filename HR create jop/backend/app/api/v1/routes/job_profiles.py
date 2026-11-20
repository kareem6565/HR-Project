import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import validate_job_description_draft
from app.ai.contracts.job_description import priority_is_explicit, quote_supports_requirement
from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.job_profiles import JobProfileCreate, JobProfileResponse, JobProfileUpdate
from app.core.database import get_db
from app.models import LinkedInJobImport
from app.services.job_profile_service import JobProfileService

router = APIRouter()


@router.patch("/job-profiles/{profile_id}", response_model=JobProfileResponse)
def update_job_profile(
    profile_id: str,
    body: JobProfileUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobProfileService().update_draft(
        db,
        profile_id=uuid.UUID(profile_id),
        organization_id=ctx.organization_id,
        edited_by_user_id=ctx.user_id,
        profile_data=body.profile_data,
    )


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
    linked_import = None
    if body.source_metadata and body.source_metadata.source_type == "linkedin":
        try:
            import_uuid = uuid.UUID(body.source_metadata.source_import_id)
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            from app.services.errors import NotFoundError

            raise NotFoundError(
                "LinkedIn import was not found or is not available for this job."
            ) from None
        linked_import = db.scalar(
            select(LinkedInJobImport)
            .where(
                LinkedInJobImport.id == import_uuid,
                LinkedInJobImport.organization_id == ctx.organization_id,
            )
            .with_for_update()
        )
        if (
            linked_import is None
            or linked_import.status != "succeeded"
            or linked_import.source_url != str(body.source_metadata.source_url)
            or (linked_import.job_id is not None and linked_import.job_id != job_uuid)
        ):
            from app.services.errors import NotFoundError

            raise NotFoundError("LinkedIn import was not found or is not available for this job.")

    provenance = None
    raw_input_snapshot = dict(body.raw_input_snapshot or {})
    if body.source_original_text is not None:
        original_text = body.source_original_text.strip()
        if original_text:
            raw_input_snapshot["original_listing_text"] = original_text
    if body.creation_method is not None:
        original_source = body.source_original_text or body.source_original_listing_text or ""
        if body.creation_method == "pasted_external" and not original_source.strip():
            from app.services.errors import ValidationError

            raise ValidationError("The original pasted description is required.")
        needs_confirmation = list(body.needs_confirmation)
        candidate_profile = dict(body.profile_data)
        candidate_profile["needs_confirmation"] = needs_confirmation
        validated_profile = validate_job_description_draft(candidate_profile)
        verified_requirements = []
        for requirement in validated_profile.requirements:
            if body.creation_method == "pasted_external":
                quote_is_present = bool(
                    requirement.source_quote
                    and requirement.source_quote in original_source
                    and quote_supports_requirement(requirement.text, requirement.source_quote)
                )
                priority_is_confirmed = requirement.category == "important" or priority_is_explicit(
                    requirement.category, requirement.source_quote
                )
                if not quote_is_present or not priority_is_confirmed:
                    requirement = requirement.model_copy(
                        update={"category": "important", "source": None, "source_quote": None}
                    )
                    needs_confirmation.append(requirement.text)
            elif requirement.source or requirement.source_quote:
                requirement = requirement.model_copy(update={"source": None, "source_quote": None})
            verified_requirements.append(requirement)
        validated_profile = validated_profile.model_copy(
            update={"requirements": verified_requirements}
        )
        profile_data = validated_profile.model_dump(
            exclude={"needs_confirmation"}, exclude_none=True
        )
        provenance = {
            "creation_method": body.creation_method,
            "created_at": datetime.now(UTC).isoformat(),
            **({"ai_extraction": {"status": "pending"}} if body.source == "ai_extracted" else {}),
            "source_url": (
                str(body.source_metadata.source_url)
                if body.source_metadata and body.source_metadata.source_url
                else None
            ),
        }
        raw_input_snapshot["creation_method"] = body.creation_method
        if needs_confirmation:
            raw_input_snapshot["needs_confirmation"] = list(dict.fromkeys(needs_confirmation))[:30]
    if body.source_metadata is not None:
        if not body.source_metadata.review_confirmed:
            from app.services.errors import ValidationError

            raise ValidationError("Confirm that you reviewed the source before saving it.")
        if not body.source_original_listing_text or not body.source_original_listing_text.strip():
            from app.services.errors import ValidationError

            raise ValidationError("The original listing text is required with source details.")
        raw_input_snapshot["original_listing_text"] = body.source_original_listing_text
        provenance = {
            **(provenance or {}),
            "source": {
                **body.source_metadata.model_dump(mode="json", exclude={"review_confirmed"}),
                "reviewed_at": datetime.now(UTC).isoformat(),
                "reviewed_by_user_id": str(ctx.user_id),
                "availability_checked_by_hera": False,
            },
            "field_origins": body.field_origins or {},
        }
        if linked_import:
            provenance["linkedin_import"] = {
                "source_type": "linkedin",
                "actor_id": linked_import.actor_id,
                "status": linked_import.status,
                "imported_at": (
                    linked_import.created_at.isoformat() if linked_import.created_at else None
                ),
                "completed_at": (
                    linked_import.finished_at.isoformat() if linked_import.finished_at else None
                ),
                "source_job_id": linked_import.source_job_id,
            }
    profile = JobProfileService().create_version(
        db,
        job_id=uuid.UUID(job_id),
        status=body.status,
        source=body.source,
        profile_data=profile_data if body.creation_method is not None else body.profile_data,
        raw_input_snapshot=raw_input_snapshot or None,
        provenance=provenance,
        organization_id=ctx.organization_id,
    )
    if linked_import:
        linked_import.job_id = job_uuid
        db.flush()
    return profile


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
        JobService().validate_for_activation(db, job)
        job.status = "active"
    return profile
