from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.candidate_portal import (
    AvailableSlotResponse,
    CandidateBookingResponse,
    CandidateBookSlotRequest,
    CandidatePortalMonthSlotsRequest,
    CandidatePortalTokenRequest,
    CandidatePortalViewResponse,
    InvitationCreateRequest,
    InvitationResponse,
)
from app.core.database import get_db
from app.models.interview_availability import InterviewAvailability
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
    issue = SchedulingWorkflowService().create_invitation(
        db,
        organization_id=ctx.organization_id,
        job_application_id=uuid.UUID(application_id),
        actor_user_id=ctx.user_id,
        expires_in_days=body.expires_in_days,
        notes=body.notes,
    )
    db.commit()
    return {
        "id": issue.invitation.id,
        "organization_id": issue.invitation.organization_id,
        "job_application_id": issue.invitation.job_application_id,
        "token": issue.token,
        "expires_at": issue.invitation.expires_at,
        "status": issue.invitation.status,
        "notes": issue.invitation.notes,
        "created_at": issue.invitation.created_at,
    }


@router.post(
    "/candidate-portal/interview/preview",
    response_model=CandidatePortalViewResponse,
)
def get_candidate_invitation_details(
    body: CandidatePortalTokenRequest,
    db: Session = Depends(get_db),
):
    """Candidate-facing endpoint: resolve invitation token and display role info.

    Strictly redacts internal scoring, AI traces, and interviewer internal notes.
    """
    view = SchedulingWorkflowService().get_candidate_view(db, body.token)
    return CandidatePortalViewResponse(**view)


@router.post(
    "/candidate-portal/interview/slots",
    response_model=list[AvailableSlotResponse],
)
def list_slots_for_invitation(
    body: CandidatePortalMonthSlotsRequest,
    db: Session = Depends(get_db),
):
    """List real open slots across the selected calendar month."""
    slots = SchedulingWorkflowService().list_available_slots_for_invitation(
        db,
        token=body.token,
        month=body.month,
    )
    return [AvailableSlotResponse(**slot) for slot in slots]


@router.post(
    "/candidate-portal/interview/book",
    response_model=CandidateBookingResponse,
    status_code=201,
)
def candidate_book_interview(
    body: CandidateBookSlotRequest,
    db: Session = Depends(get_db),
):
    """Candidate selects and books an offered interview slot.

    Protected by database row locking to prevent concurrent double-booking.
    """
    interview = SchedulingWorkflowService().candidate_book_slot(
        db,
        token=body.token,
        availability_id=body.availability_id,
        scheduled_time=body.scheduled_time,
    )
    db.commit()
    availability = db.get(InterviewAvailability, body.availability_id)
    return CandidateBookingResponse(
        status=interview.status,
        scheduled_date=interview.scheduled_date.isoformat(),
        scheduled_time=interview.scheduled_time,
        scheduled_duration_minutes=interview.scheduled_duration_minutes,
        timezone=availability.timezone if availability is not None else "UTC",
    )
