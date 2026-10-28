from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidate_portal import (
    AvailabilityCreateRequest,
    AvailabilityResponse,
)
from app.core.database import get_db
from app.services.scheduling_workflow_service import SchedulingWorkflowService

router = APIRouter()


@router.post(
    "/availability",
    response_model=AvailabilityResponse,
    status_code=201,
)
def publish_interviewer_availability(
    body: AvailabilityCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Publish genuine interviewer availability for candidate self-scheduling."""
    avail = SchedulingWorkflowService().publish_availability(
        db,
        organization_id=ctx.organization_id,
        interviewer_user_id=body.interviewer_user_id,
        scheduled_date=body.scheduled_date,
        start_time=body.start_time,
        end_time=body.end_time,
        duration_minutes=body.duration_minutes,
        timezone_name=body.timezone,
    )
    db.commit()
    return avail


@router.get(
    "/availability",
    response_model=list[AvailabilityResponse],
)
def list_availability(
    scheduled_date: date | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    interviewer_user_id: str | None = Query(default=None),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """List published open interview availability blocks for the organization."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    interviewer_id = uuid.UUID(interviewer_user_id) if interviewer_user_id else None

    return SchedulingWorkflowService().list_availability(
        db,
        organization_id=ctx.organization_id,
        scheduled_date=scheduled_date,
        start_date=start_date,
        end_date=end_date,
        interviewer_user_id=interviewer_id,
    )


@router.delete(
    "/availability/{availability_id}",
    response_model=AvailabilityResponse,
)
def withdraw_interviewer_availability(
    availability_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    availability = SchedulingWorkflowService().cancel_availability(
        db,
        organization_id=ctx.organization_id,
        availability_id=uuid.UUID(availability_id),
    )
    db.commit()
    return availability
