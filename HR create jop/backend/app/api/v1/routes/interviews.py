import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.interviews import (
    InterviewCancel,
    InterviewCreate,
    InterviewerResponse,
    InterviewFeedbackCreate,
    InterviewListResponse,
    InterviewResponse,
)
from app.core.database import get_db
from app.services.interview_service import InterviewService

router = APIRouter()


@router.get(
    "/interview-slots",
)
def list_interview_slots(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    scheduled_date: str | None = Query(default=None),
    interviewer_user_id: str | None = Query(default=None),
):
    """Return occupied interview windows for a date (optionally per interviewer)."""
    from datetime import date

    parsed_date = date.fromisoformat(scheduled_date) if scheduled_date else None
    if parsed_date is None:
        from app.services.errors import ValidationError

        raise ValidationError("scheduled_date is required as YYYY-MM-DD.")
    occupied = InterviewService().list_slots_for_date(
        db,
        organization_id=ctx.organization_id,
        scheduled_date=parsed_date,
        interviewer_user_id=uuid.UUID(interviewer_user_id) if interviewer_user_id else None,
    )
    return {"date": parsed_date.isoformat(), "occupied": occupied, "total": len(occupied)}


@router.get(
    "/interviewers",
    response_model=list[InterviewerResponse],
)
def list_interviewers(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Return org users available to run interviews."""
    users = InterviewService().list_interviewers(db, organization_id=ctx.organization_id)
    return [
        InterviewerResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
        )
        for user in users
    ]


@router.get(
    "/interviews",
    response_model=InterviewListResponse,
)
def list_interviews(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
):
    """List org interviews, newest first, optionally filtered by status."""
    interviews = InterviewService().list(
        db,
        organization_id=ctx.organization_id,
        status=status,
    )
    return InterviewListResponse(
        interviews=[
            InterviewResponse(**InterviewService.to_response(interview)) for interview in interviews
        ],
        total=len(interviews),
    )


@router.get(
    "/interviews/{interview_id}",
    response_model=InterviewResponse,
)
def get_interview(
    interview_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    interview = InterviewService().get(
        db,
        interview_id=uuid.UUID(interview_id),
        organization_id=ctx.organization_id,
    )
    return InterviewResponse(**InterviewService.to_response(interview))


@router.post(
    "/interviews",
    response_model=InterviewResponse,
    status_code=201,
)
def schedule_interview(
    body: InterviewCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    interview = InterviewService().schedule(
        db,
        organization_id=ctx.organization_id,
        candidate_id=body.candidate_id,
        job_id=body.job_id,
        interview_type=body.interview_type,
        scheduled_date=body.scheduled_date,
        scheduled_time=body.scheduled_time,
        interviewer_user_id=body.interviewer_user_id,
        meeting_link=body.meeting_link,
        scheduled_duration_minutes=body.scheduled_duration_minutes,
        interview_question_set_id=body.interview_question_set_id,
    )
    db.commit()
    return InterviewResponse(**InterviewService.to_response(interview))


@router.patch(
    "/interviews/{interview_id}",
    response_model=InterviewResponse,
)
def cancel_interview(
    interview_id: str,
    body: InterviewCancel,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    interview = InterviewService().cancel(
        db,
        interview_id=uuid.UUID(interview_id),
        organization_id=ctx.organization_id,
    )
    db.commit()
    return InterviewResponse(**InterviewService.to_response(interview))


@router.post(
    "/interviews/{interview_id}/feedback",
    response_model=InterviewResponse,
)
def submit_interview_feedback(
    interview_id: str,
    body: InterviewFeedbackCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    interview = InterviewService().submit_feedback(
        db,
        interview_id=uuid.UUID(interview_id),
        organization_id=ctx.organization_id,
        feedback=body.model_dump(),
    )
    db.commit()
    return InterviewResponse(**InterviewService.to_response(interview))
