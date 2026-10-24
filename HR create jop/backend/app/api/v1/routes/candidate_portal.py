from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidate_portal import (
    AvailableSlotResponse,
    CandidateBookSlotRequest,
    CandidatePortalViewResponse,
    InvitationCreateRequest,
    InvitationResponse,
)
from app.api.v1.schemas.interviews import InterviewResponse
from app.core.database import get_db
from app.services.interview_service import InterviewService
from app.services.scheduling_workflow_service import SchedulingWorkflowService

router = APIRouter()


@router.post(
    "/job-applications/{application_id}/invitations",
    response_model=InvitationResponse,
    status_code=201,
)
def create_candidate_invitation(
    application_id: str,
    body: InvitationCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Generate a candidate self-scheduling invitation (HR-authenticated).

    Enforces Stage G: Advance Gate — application must have an authoritative HR 'advance' decision.
    """
    invitation = SchedulingWorkflowService().create_invitation(
        db,
        organization_id=ctx.organization_id,
        job_application_id=uuid.UUID(application_id),
        actor_user_id=ctx.user_id,
        expires_in_days=body.expires_in_days,
        notes=body.notes,
    )
    db.commit()
    return invitation


@router.get(
    "/candidate-portal/invitations/{token}",
    response_model=CandidatePortalViewResponse,
)
def get_candidate_invitation_details(
    token: str,
    db: Session = Depends(get_db),
):
    """Candidate-facing endpoint: resolve invitation token and display role info.

    Strictly redacts internal scoring, AI traces, and interviewer internal notes.
    """
    view = SchedulingWorkflowService().get_candidate_view(db, token)
    return CandidatePortalViewResponse(**view)


@router.get(
    "/candidate-portal/invitations/{token}/slots",
    response_model=list[AvailableSlotResponse],
)
def list_slots_for_invitation(
    token: str,
    date_filter: str | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    """Candidate-facing endpoint: list genuinely open, non-conflicting interview slots."""
    parsed_date = date.fromisoformat(date_filter) if date_filter else None
    slots = SchedulingWorkflowService().list_available_slots_for_invitation(
        db,
        token=token,
        scheduled_date=parsed_date,
    )
    return [AvailableSlotResponse(**slot) for slot in slots]


@router.post(
    "/candidate-portal/invitations/{token}/book",
    response_model=InterviewResponse,
    status_code=201,
)
def candidate_book_interview(
    token: str,
    body: CandidateBookSlotRequest,
    db: Session = Depends(get_db),
):
    """Candidate selects and books an offered interview slot.

    Protected by database row locking to prevent concurrent double-booking.
    """
    interview = SchedulingWorkflowService().candidate_book_slot(
        db,
        token=token,
        scheduled_date=body.scheduled_date,
        scheduled_time=body.scheduled_time,
        duration_minutes=body.duration_minutes,
        interviewer_user_id=body.interviewer_user_id,
    )
    db.commit()
    return InterviewResponse(**InterviewService.to_response(interview))


@router.post(
    "/candidate-portal/invitations/{token}/cancel",
    response_model=InterviewResponse,
)
def candidate_cancel_interview(
    token: str,
    interview_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Candidate-facing cancellation of an appointment."""
    cancelled = SchedulingWorkflowService().candidate_cancel_booking(
        db,
        token=token,
        interview_id=uuid.UUID(interview_id),
    )
    db.commit()
    return InterviewResponse(**InterviewService.to_response(cancelled))
