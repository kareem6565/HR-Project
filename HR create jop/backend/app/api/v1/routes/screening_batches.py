import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.core.config import settings
from app.core.database import get_db
from app.models import CandidateEvaluation, ScreeningBatch
from app.services.screening_batch_service import ScreeningBatchService
from app.services.storage_service import LocalFileSystemStorage
from app.services.upload_stream_service import read_batch_bounded

router = APIRouter()


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
        result.append({
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
        })
    return result


@router.post(
    "/jobs/{job_id}/screening-batches",
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_screening_batch(
    job_id: str,
    files: list[UploadFile] = File(...),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Submit a batch of CV files for asynchronous processing.

    Enforces file count and payload limits, authenticates organization scope,
    and returns 202 Accepted with the batch ID.
    """
    job_uuid = uuid.UUID(job_id)

    # Bounded chunked streaming read
    payloads = read_batch_bounded(
        files,
        max_files=settings.max_batch_files,
        max_file_bytes=settings.max_upload_bytes,
        max_batch_bytes=settings.max_batch_bytes,
    )

    storage = LocalFileSystemStorage(settings.storage_root_dir)
    service = ScreeningBatchService()
    batch = service.create_batch(
        db,
        organization_id=ctx.organization_id,
        job_id=job_uuid,
        user_id=ctx.user_id,
        payloads=payloads,
        storage=storage,
    )
    db.commit()

    queued_initial = batch.total_files - len([it for it in batch.items if it.status == "duplicate"])
    dup_initial = len([it for it in batch.items if it.status == "duplicate"])

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
                "failed": 0,
                "duplicate": dup_initial,
                "cancelled": 0,
            },
            "queued_items": queued_initial,
            "running_items": 0,
            "done_items": 0,
            "failed_items": 0,
            "duplicate_items": dup_initial,
            "cancelled_items": 0,
            "items": [
                {
                    "id": str(item.id),
                    "filename": item.filename,
                    "original_filename": item.filename,
                    "status": item.status,
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

    for it in batch.items:
        if it.status == "queued":
            queued_c += 1
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
                "status": it.status,
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
                "created_at": it.created_at.isoformat(),
                "updated_at": it.updated_at.isoformat(),
            }
        )

    return {
        "id": str(batch.id),
        "batch_id": str(batch.id),
        "job_id": str(batch.job_id),
        "status": batch.status,
        "total_files": batch.total_files,
        "total_items": batch.total_files,
        "counts": {
            "total": batch.total_files,
            "queued": queued_c,
            "running": running_c,
            "completed": done_c,
            "failed": failed_c,
            "duplicate": duplicate_c,
            "cancelled": cancelled_c,
        },
        "queued_items": queued_c,
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
