import hashlib
import logging
import uuid
from io import BytesIO
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.jobs import JobCreate, JobResponse, JobUpdate, PublicJobResponse
from app.api.v1.schemas.public_applications import (
    PublicApplicationConfigResponse,
    PublicApplicationResponse,
)
from app.core.config import settings
from app.core.database import get_db
from app.models import Job, JobApplication
from app.services.errors import UploadValidationError
from app.services.job_service import JobService
from app.services.public_application_service import PublicApplicationService
from app.services.job_distribution_service import JobDistributionService
from app.services.upload_stream_service import read_upload_file_bounded

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/jobs", response_model=JobResponse, status_code=201)
def create_job(
    body: JobCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
):
    return JobService().create(
        db,
        organization_id=ctx.organization_id,
        title=body.title,
        raw_description=body.raw_description,
        description_text=body.description_text,
        status=body.status,
        department=body.department,
        location=body.location,
        job_type=body.job_type,
        work_mode=body.work_mode,
        experience=body.experience,
        requirements=body.requirements,
        required_skills=body.required_skills,
        created_by_user_id=ctx.user_id,
        idempotency_key=idempotency_key,
    )


@router.put("/jobs/{job_id}/source-file", response_model=JobResponse)
def upload_job_source_file(
    job_id: str,
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Retain the original job file even when text extraction cannot process it."""
    import re

    from app.services.storage_service import LocalFileSystemStorage
    from app.services.text_extraction_service import extract_text
    from app.services.upload_stream_service import read_upload_file_bounded

    job = JobService().get(db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id)
    payload, _, _ = read_upload_file_bounded(file, max_bytes=settings.max_upload_bytes)
    filename = (file.filename or "job-description").replace("\\", "/").rsplit("/", 1)[-1]
    extension = re.sub(r"[^a-zA-Z0-9]", "", filename.rsplit(".", 1)[-1]).lower()
    storage = LocalFileSystemStorage(settings.storage_root_dir)
    uri = storage.save_job_file(
        organization_id=ctx.organization_id,
        job_id=job.id,
        extension=extension or "bin",
        stream=lambda: payload,
    )
    job.source_file_uri = uri
    job.source_file_name = filename[:255]
    job.source_file_text = None
    job.source_file_sha256 = hashlib.sha256(payload).hexdigest()
    job.source_file_status = "pending"
    job.source_file_error = None
    db.flush()
    db.commit()

    try:
        job.source_file_text = extract_text(
            payload,
            filename=filename,
            max_pdf_pages=settings.max_pdf_pages,
            max_docx_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
            max_docx_entries=settings.max_docx_entries,
        )
        job.source_file_status = "ready"
    except UploadValidationError as error:
        job.source_file_status = "failed"
        job.source_file_error = str(error)
    except Exception:
        # The original has already been safely stored. Avoid losing the vacancy
        # or file because a parser unexpectedly failed; allow a corrected retry.
        logger.exception("Unexpected job description text extraction failure for job %s", job.id)
        job.source_file_status = "failed"
        job.source_file_error = "The file was saved, but its text could not be extracted."
    db.commit()
    return job


@router.get("/jobs/{job_id}/source-file")
def download_job_source_file(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Download the original uploaded job description within its organization."""
    from app.services.errors import NotFoundError
    from app.services.storage_service import LocalFileSystemStorage

    job = JobService().get(db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id)
    if not job.source_file_uri:
        raise NotFoundError("This vacancy has no uploaded source file.")
    content = LocalFileSystemStorage(settings.storage_root_dir).read(file_uri=job.source_file_uri)
    filename = (job.source_file_name or "job-description").replace('"', "")
    filename = filename.replace("\r", "").replace("\n", "")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"job-description\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobService().list(db, organization_id=ctx.organization_id)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    JobService().delete(db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobService().get(db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    body: JobUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return JobService().update(
        db,
        job_id=uuid.UUID(job_id),
        organization_id=ctx.organization_id,
        title=body.title,
        raw_description=body.raw_description,
        description_text=body.description_text,
        status=body.status,
        department=body.department,
        location=body.location,
        job_type=body.job_type,
        work_mode=body.work_mode,
        clear_work_mode="work_mode" in body.model_fields_set and body.work_mode is None,
        experience=body.experience,
        requirements=body.requirements,
        required_skills=body.required_skills,
    )


@router.post("/jobs/{job_id}/publish", response_model=JobResponse)
def publish_job(
    job_id: str, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)
):
    return JobService().publish(
        db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id, actor_user_id=ctx.user_id
    )


@router.post("/jobs/{job_id}/close", response_model=JobResponse)
def close_public_job(
    job_id: str, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)
):
    return JobService().close_publication(
        db, job_id=uuid.UUID(job_id), organization_id=ctx.organization_id, actor_user_id=ctx.user_id
    )


public_router = APIRouter()


@public_router.get("/public/jobs/{public_id}", response_model=PublicJobResponse)
def get_public_job(
    public_id: str,
    response: Response,
    utm_campaign: Annotated[str | None, Query(max_length=100)] = None,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    details = JobService().public_details(db, public_id=public_id)
    if details["accepting_applications"]:
        JobDistributionService().record_view(
            db, public_id=public_id, tracking_key=utm_campaign
        )
    return details


@public_router.get("/public/application-config", response_model=PublicApplicationConfigResponse)
def get_public_application_config():
    notice_available = PublicApplicationService.privacy_notice_available()
    return PublicApplicationConfigResponse(
        notice_available=notice_available,
        privacy_notice_text=(
            settings.application_privacy_notice_text if notice_available else None
        ),
        privacy_notice_version=(
            settings.application_privacy_notice_version if notice_available else None
        ),
        turnstile_required=settings.turnstile_required,
        turnstile_server_configured=bool(settings.turnstile_secret_key),
        max_upload_bytes=settings.max_upload_bytes,
    )


@public_router.post(
    "/public/jobs/{public_id}/applications",
    response_model=PublicApplicationResponse,
    status_code=201,
)
def submit_public_application(
    public_id: str,
    request: Request,
    resume: Annotated[UploadFile, File(...)],
    full_name: Annotated[str, Form(...)],
    email: Annotated[str, Form(...)],
    privacy_accepted: Annotated[bool, Form(...)],
    privacy_notice_version: Annotated[str, Form(...)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
    phone: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    github_url: Annotated[str | None, Form()] = None,
    portfolio_url: Annotated[str | None, Form()] = None,
    turnstile_token: Annotated[str | None, Form()] = None,
    utm_source: Annotated[str | None, Form()] = None,
    utm_medium: Annotated[str | None, Form()] = None,
    utm_campaign: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    service = PublicApplicationService()
    if not service.privacy_notice_available():
        return JSONResponse(
            status_code=503,
            content={"detail": "Applications are temporarily unavailable."},
        )

    if not service.consume_rate_limit(
        db, client_host=request.client.host if request.client else None
    ):
        logger.warning(
            "Public job application rate limit reached", extra={"public_job_id": public_id}
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many applications from this network. Try again later."},
            headers={"Retry-After": str(max(1, settings.public_application_rate_window_seconds))},
        )
    original_filename = (resume.filename or "resume").replace("\\", "/").rsplit("/", 1)[-1]
    if len(original_filename) > 255:
        return JSONResponse(status_code=422, content={"detail": "Resume filename is too long."})
    file_bytes, _, checksum = read_upload_file_bounded(resume, max_bytes=settings.max_upload_bytes)
    try:
        reference, _replayed = service.submit(
            db,
            public_id=public_id,
            idempotency_key=idempotency_key,
            full_name=full_name,
            email=email,
            phone=phone,
            linkedin_url=linkedin_url,
            github_url=github_url,
            portfolio_url=portfolio_url,
            resume_filename=original_filename,
            resume_content_type=resume.content_type or "",
            resume_bytes=file_bytes,
            resume_checksum=checksum,
            privacy_accepted=privacy_accepted,
            privacy_notice_version=privacy_notice_version,
            turnstile_token=turnstile_token,
            source=request.query_params.get("utm_source") or utm_source,
            source_medium=request.query_params.get("utm_medium") or utm_medium,
            source_campaign=request.query_params.get("utm_campaign") or utm_campaign,
        )
    except IntegrityError:
        job = db.scalar(select(Job).where(Job.public_id == public_id))
        existing = (
            db.scalar(
                select(JobApplication).where(
                    JobApplication.organization_id == job.organization_id,
                    JobApplication.job_id == job.id,
                    JobApplication.idempotency_key_hash
                    == hashlib.sha256(idempotency_key.encode()).hexdigest(),
                )
            )
            if job
            else None
        )
        if existing and existing.public_reference:
            return PublicApplicationResponse(
                application_reference=existing.public_reference,
                message="Your application has been received.",
            )
        raise
    logger.info("Public job application accepted", extra={"public_job_id": public_id})
    return PublicApplicationResponse(
        application_reference=reference,
        message="Your application has been received.",
    )
