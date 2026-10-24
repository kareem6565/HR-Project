import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.resumes import ResumeResponse
from app.core.config import settings
from app.core.database import get_db
from app.services.resume_service import ResumeService
from app.services.storage_service import LocalFileSystemStorage
from app.services.upload_stream_service import read_upload_file_bounded

router = APIRouter()


@router.post(
    "/candidates/{candidate_id}/resumes/upload",
    response_model=ResumeResponse,
    status_code=201,
)
def upload_resume(
    candidate_id: str,
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    file_bytes, _size, checksum = read_upload_file_bounded(
        file, max_bytes=settings.max_upload_bytes
    )
    return ResumeService().create_from_upload(
        db,
        candidate_id=uuid.UUID(candidate_id),
        organization_id=ctx.organization_id,
        filename=file.filename or "",
        content_type=file.content_type or "",
        file_bytes=file_bytes,
        max_upload_bytes=settings.max_upload_bytes,
        storage=LocalFileSystemStorage(settings.storage_root_dir),
        checksum=checksum,
    )


@router.get("/resumes/{resume_id}", response_model=ResumeResponse)
def get_resume(
    resume_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return ResumeService().get(
        db, resume_id=uuid.UUID(resume_id), organization_id=ctx.organization_id
    )


def sanitize_download_filename(filename: str | None, default: str = "resume.pdf") -> str:
    """Sanitize filename to prevent CR/LF header injection, path traversal, and quote escaping."""
    if not filename:
        return default
    # Remove CR, LF, nulls, and non-printable control characters
    cleaned = "".join(ch for ch in filename if 32 <= ord(ch) < 127)
    # Extract basename to prevent directory traversal
    name = Path(cleaned).name.strip()
    # Replace quotes, semicolons, backslashes and special characters with underscore
    safe = re.sub(r"[^a-zA-Z0-9._ -]", "_", name)
    safe = safe.strip(" .")
    if not safe:
        return default
    return safe


@router.get("/resumes/{resume_id}/download")
def download_resume(
    resume_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Stream the raw CV bytes for a resume the organization owns.

    Returns the original file with its stored content type and a
    sanitized ``Content-Disposition`` attachment header so browsers download it safely.
    """
    resume = ResumeService().get(
        db, resume_id=uuid.UUID(resume_id), organization_id=ctx.organization_id
    )
    storage = LocalFileSystemStorage(settings.storage_root_dir)
    content = storage.read(file_uri=resume.file_uri)
    media_type = resume.content_type or "application/octet-stream"
    filename = sanitize_download_filename(resume.original_filename)

    from app.services.audit_service import AuditService

    AuditService().log_event(
        db,
        action="resume.downloaded",
        entity_type="resume",
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        entity_id=resume.id,
        metadata={
            "candidate_id": str(resume.candidate_id),
            "filename": filename,
        },
        flush=True,
    )
    db.commit()

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
