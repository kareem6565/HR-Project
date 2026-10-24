import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.ai_activity import (
    AIActivityRetryResponse,
    AIActivityRunResponse,
    AIActivityStatsResponse,
)
from app.core.database import get_db
from app.services.ai_activity_service import AIActivityService

router = APIRouter()


@router.get(
    "/ai-activity/runs",
    response_model=list[AIActivityRunResponse],
)
def list_ai_activity_runs(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List org workflow runs with step + AI component breakdowns, newest first."""
    views = AIActivityService().list_runs(
        db,
        organization_id=ctx.organization_id,
        limit=limit,
    )
    return [AIActivityRunResponse(**view) for view in views]


@router.get(
    "/ai-activity/stats",
    response_model=AIActivityStatsResponse,
)
def get_ai_activity_stats(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Return last-24h run counts and average AI latency, org-scoped."""
    stats = AIActivityService().get_stats(db, organization_id=ctx.organization_id)
    return AIActivityStatsResponse(**stats)


@router.post(
    "/ai-activity/runs/{run_id}/retry",
    response_model=AIActivityRetryResponse,
)
def retry_ai_activity_run(
    run_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Re-run a failed workflow run against its related entity."""
    from app.services.errors import NotFoundError, ValidationError

    try:
        return AIActivityService().retry_run(
            db,
            organization_id=ctx.organization_id,
            workflow_run_id=uuid.UUID(run_id),
        )
    except ValidationError as err:
        if "organization" in str(err).lower():
            raise NotFoundError("Workflow run was not found.") from err
        raise
