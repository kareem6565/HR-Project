import uuid as _uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.workflows import AITraceResponse, WorkflowRunResponse
from app.core.database import get_db
from app.services.observability_service import ObservabilityService

router = APIRouter()


@router.get(
    "/workflow-runs/{run_id}",
    response_model=WorkflowRunResponse,
)
def get_workflow_run(
    run_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return ObservabilityService().get_workflow_run(
        db,
        workflow_run_id=_uuid.UUID(run_id),
        organization_id=ctx.organization_id,
    )


@router.get(
    "/ai-traces/{trace_id}",
    response_model=AITraceResponse,
)
def get_ai_trace(
    trace_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    return ObservabilityService().get_ai_trace(
        db,
        ai_trace_id=_uuid.UUID(trace_id),
        organization_id=ctx.organization_id,
    )
