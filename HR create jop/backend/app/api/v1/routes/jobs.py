import hashlib
import logging
import uuid
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.jobs import JobCreate, JobResponse, JobUpdate
from app.core.config import settings
from app.core.database import get_db
from app.services.errors import UploadValidationError
from app.services.job_service import JobService

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
                f'attachment; filename="job-description"; filename*=UTF-8\'\'{quote(filename)}'
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
        experience=body.experience,
        requirements=body.requirements,
        required_skills=body.required_skills,
    )
