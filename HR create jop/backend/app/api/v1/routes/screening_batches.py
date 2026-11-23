import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.core.config import settings
from app.core.database import get_db
from app.models import CandidateEvaluation, Job, ScreeningBatch
from app.services.errors import NotFoundError, UploadValidationError
from app.services.screening_batch_service import ScreeningBatchService
from app.services.storage_service import LocalFileSystemStorage
from app.services.upload_stream_service import read_batch_bounded, read_zip_batch_bounded

router = APIRouter()


@router.get("/screening-upload-config")
def get_screening_upload_config() -> dict[str, int]:
    """Return authoritative upload limits for the recruitment UI."""
    return {
        "max_file_bytes": settings.max_upload_bytes,
        "max_batch_files": settings.max_batch_files,
        "max_batch_bytes": settings.max_batch_bytes,
        "max_zip_entries": settings.max_zip_entries,
        "max_zip_total_bytes": settings.max_zip_total_bytes,
        "max_zip_archive_bytes": settings.max_zip_archive_bytes,
        "max_zip_compression_ratio": settings.max_zip_compression_ratio,
        "max_concurrent_batches_per_org": settings.max_concurrent_batches_per_org,
    }


@router.get("/jobs/{job_id}/screening-batches")
def list_job_screening_batches(
    job_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List recent screening batches for a job, scoped to the caller's organization."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        return []
    stmt = (
        select(ScreeningBatch)
        .where(
            ScreeningBatch.job_id == job_uuid,
            ScreeningBatch.organization_id == ctx.organization_id,
        )
        .order_by(ScreeningBatch.created_at.desc())
        .limit(limit)
    )
    batches = db.execute(stmt).scalars().all()
    result = []
    for batch in batches:
        items = list(batch.items)
        queued_c = sum(1 for it in items if it.status == "queued")
        running_c = sum(1 for it in items if it.status == "running")
        done_c = sum(1 for it in items if it.status == "done")
        failed_c = sum(1 for it in items if it.status == "failed")
        duplicate_c = sum(1 for it in items if it.status == "duplicate")
        result.append(
            {
                "id": str(batch.id),
                "batch_id": str(batch.id),
                "job_id": str(batch.job_id),
                "status": batch.status,
                "total_files": batch.total_files,
                "counts": {
                    "total": batch.total_files,
                    "queued": queued_c,
                    "running": running_c,
                    "completed": done_c,
                    "failed": failed_c,
                    "duplicate": duplicate_c,
                },
                "created_at": batch.created_at.isoformat(),
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            }
        )
    return result


@router.post(
    "/jobs/{job_id}/screening-batches",
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_screening_batch(
    job_id: str,
    files: list[UploadFile] | None = File(default=None),
    archive: UploadFile | None = File(default=None),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Submit a batch of CV files for asynchronous processing.

    Enforces file count and payload limits, authenticates organization scope,
    and returns 202 Accepted with the batch ID.
    """
    job_uuid = uuid.UUID(job_id)

    if (
        db.scalar(
            select(Job.id).where(Job.id == job_uuid, Job.organization_id == ctx.organization_id)
        )
        is None
    ):
        raise NotFoundError("Job was not found.")
    # Reserve an org-scoped slot transactionally before accepting expensive payloads.
    service = ScreeningBatchService()
    service.reserve_org_batch_slot(
        db,
        organization_id=ctx.organization_id,
        limit=settings.max_concurrent_batches_per_org,
    )
    storage = LocalFileSystemStorage(settings.storage_root_dir)
    if archive is not None:
        if files:
            raise UploadValidationError(
                "Upload either individual files or one ZIP archive, not both.",
                code="INVALID_ARCHIVE",
            )
        payloads = read_zip_batch_bounded(
            archive,
            max_entries=settings.max_zip_entries,
            max_files=settings.max_batch_files,
            max_file_bytes=settings.max_upload_bytes,
            max_total_bytes=settings.max_zip_total_bytes,
            max_compression_ratio=settings.max_zip_compression_ratio,
            max_archive_bytes=settings.max_zip_archive_bytes,
            staging_root=settings.storage_root_dir,
        )
    else:
        payloads = read_batch_bounded(
            files or [],
            max_files=settings.max_batch_files,
            max_file_bytes=settings.max_upload_bytes,
            max_batch_bytes=settings.max_batch_bytes,
        )
    batch = service.create_batch(
        db,
        organization_id=ctx.organization_id,
        job_id=job_uuid,
        user_id=ctx.user_id,
        payloads=payloads,
        storage=storage,
        max_concurrent_batches=settings.max_concurrent_batches_per_org,
    )
    from app.services.audit_service import AuditService

    AuditService().log_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="screening.batch_created",
        entity_type="screening_batch",
        entity_id=batch.id,
        metadata={
            "total_files": batch.total_files,
            "failed_count": batch.failed_files,
            "duplicate_count": sum(item.status == "duplicate" for item in batch.items),
        },
    )
    db.commit()

    queued_initial = sum(item.status == "queued" for item in batch.items)
    failed_initial = sum(item.status == "failed" for item in batch.items)
    dup_initial = sum(item.status == "duplicate" for item in batch.items)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "id": str(batch.id),
            "batch_id": str(batch.id),
            "job_id": str(batch.job_id),
            "status": batch.status,
            "total_files": batch.total_files,
            "total_items": batch.total_files,
            "counts": {
                "total": batch.total_files,
                "queued": queued_initial,
                "running": 0,
                "completed": 0,
                "failed": failed_initial,
                "duplicate": dup_initial,
                "cancelled": 0,
            },
            "queued_items": queued_initial,
            "running_items": 0,
            "done_items": 0,
            "failed_items": failed_initial,
            "duplicate_items": dup_initial,
            "cancelled_items": 0,
            "items": [
                {
                    "id": str(item.id),
                    "filename": item.filename,
                    "original_filename": item.filename,
                    "status": item.status,
                    "reason": item.error_message,
                }
                for item in batch.items
            ],
        },
    )


@router.get("/screening-batches/{batch_id}")
def get_screening_batch(
    batch_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve the progress and per-file results of a screening batch."""
    service = ScreeningBatchService()
    batch = service.get_batch(
        db,
        batch_id=uuid.UUID(batch_id),
        organization_id=ctx.organization_id,
    )

    items_data = []
    queued_c = 0
    running_c = 0
    done_c = 0
    failed_c = 0
    duplicate_c = 0
    cancelled_c = 0
    waiting_quota_c = 0

    for it in batch.items:
        if it.status == "queued":
            queued_c += 1
            if it.stage == "waiting_for_quota":
                waiting_quota_c += 1
        elif it.status == "running":
            running_c += 1
        elif it.status == "done":
            done_c += 1
        elif it.status == "failed":
            failed_c += 1
        elif it.status == "duplicate":
            duplicate_c += 1
        elif it.status == "cancelled":
            cancelled_c += 1

        score = None
        if it.evaluation_id:
            ev = db.get(CandidateEvaluation, it.evaluation_id)
            if ev and ev.score is not None:
                score = str(ev.score)

        items_data.append(
            {
                "id": str(it.id),
                "filename": it.filename,
                "original_filename": it.filename,
                "status": "waiting_for_quota"
                if it.stage == "waiting_for_quota" and it.status == "queued"
                else it.status,
                "stage": it.stage,
                "attempts": it.attempts,
                "retry_count": it.attempts,
                "max_attempts": it.max_attempts,
                "candidate_id": str(it.candidate_id) if it.candidate_id else None,
                "application_id": str(it.application_id) if it.application_id else None,
                "evaluation_id": str(it.evaluation_id) if it.evaluation_id else None,
                "score": score,
                "error_code": it.error_code,
                "error_message": it.error_message,
                "reason": it.error_message,
                "created_at": it.created_at.isoformat(),
                "updated_at": it.updated_at.isoformat(),
            }
        )

    terminal_count = done_c + failed_c + duplicate_c + cancelled_c
    batch_created_at = batch.created_at
    if batch_created_at.tzinfo is None:
        batch_created_at = batch_created_at.replace(tzinfo=UTC)
    elapsed_seconds = max((datetime.now(UTC) - batch_created_at).total_seconds(), 0.0)
    rate = terminal_count / elapsed_seconds if terminal_count >= 3 and elapsed_seconds > 0 else None
    remaining = max(batch.total_files - terminal_count, 0)
    eta_seconds = int(remaining / rate) if rate else None
    return {
        "id": str(batch.id),
        "batch_id": str(batch.id),
        "job_id": str(batch.job_id),
        "status": batch.status,
        "total_files": batch.total_files,
        "total_items": batch.total_files,
        "eta_seconds": eta_seconds,
        "eta_label": "unknown" if eta_seconds is None else f"about {eta_seconds} seconds",
        "counts": {
            "total": batch.total_files,
            "queued": queued_c,
            "waiting_for_quota": waiting_quota_c,
            "running": running_c,
            "completed": done_c,
            "failed": failed_c,
            "duplicate": duplicate_c,
            "cancelled": cancelled_c,
        },
        "queued_items": queued_c,
        "waiting_for_quota_items": waiting_quota_c,
        "running_items": running_c,
        "done_items": done_c,
        "failed_items": failed_c,
        "duplicate_items": duplicate_c,
        "cancelled_items": cancelled_c,
        "created_at": batch.created_at.isoformat(),
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "items": items_data,
    }


@router.post("/screening-batch-items/{item_id}/retry")
def retry_screening_batch_item(
    item_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retry an eligible failed screening batch item."""
    service = ScreeningBatchService()
    item = service.retry_item(
        db,
        item_id=uuid.UUID(item_id),
        organization_id=ctx.organization_id,
    )
    db.commit()

    return {
        "id": str(item.id),
        "batch_id": str(item.batch_id),
        "filename": item.filename,
        "status": item.status,
        "stage": item.stage,
        "attempts": item.attempts,
        "max_attempts": item.max_attempts,
    }
