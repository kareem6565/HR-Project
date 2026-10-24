from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CandidateInvitation,
    Interview,
    InterviewAvailability,
    JobApplication,
    Organization,
    User,
)
from app.services.audit_service import AuditService
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.interview_service import (
    DEFAULT_DURATION_MINUTES,
    InterviewService,
    _conflict_message,
    _to_hhmm,
    _to_minutes,
)


class SchedulingWorkflowService:
    """Manages interviewer availability, candidate invitations, and candidate self-scheduling."""

    def publish_availability(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        interviewer_user_id: uuid.UUID,
        scheduled_date: date,
        start_time: str,
        end_time: str,
        duration_minutes: int = DEFAULT_DURATION_MINUTES,
        timezone_name: str = "UTC",
    ) -> InterviewAvailability:
        """Publish genuine interviewer availability for candidate scheduling."""
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization was not found.")

        interviewer = db.get(User, interviewer_user_id)
        if interviewer is None or interviewer.organization_id != organization_id:
            raise NotFoundError("Interviewer was not found.")

        start_min = _to_minutes(start_time)
        end_min = _to_minutes(end_time)
        if end_min <= start_min:
            raise ValidationError("end_time must be after start_time.")
        if duration_minutes < 15 or duration_minutes > (end_min - start_min):
            raise ValidationError(
                f"duration_minutes ({duration_minutes}) must be between 15 and the window size ({end_min - start_min})."
            )

        availability = InterviewAvailability(
            organization_id=organization_id,
            interviewer_user_id=interviewer_user_id,
            scheduled_date=scheduled_date,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            timezone=timezone_name,
            status="available",
        )
        db.add(availability)
        db.flush()
        return availability

    def list_availability(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        scheduled_date: date | None = None,
        interviewer_user_id: uuid.UUID | None = None,
    ) -> list[InterviewAvailability]:
        """List published availabilities matching filters."""
        stmt = (
            select(InterviewAvailability)
            .where(
                InterviewAvailability.organization_id == organization_id,
                InterviewAvailability.status == "available",
            )
            .order_by(
                InterviewAvailability.scheduled_date,
                InterviewAvailability.start_time,
            )
        )
        if scheduled_date is not None:
            stmt = stmt.where(InterviewAvailability.scheduled_date == scheduled_date)
        if interviewer_user_id is not None:
            stmt = stmt.where(InterviewAvailability.interviewer_user_id == interviewer_user_id)
        return list(db.scalars(stmt))

    def create_invitation(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        job_application_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        expires_in_days: int = 7,
        notes: str | None = None,
    ) -> CandidateInvitation:
        """Issue a secure, candidate-facing interview invitation token.

        Enforces Stage G: Advance Gate — candidates cannot be invited for interviews
        unless HR has made an authoritative 'advance' decision.
        """
        application = db.get(JobApplication, job_application_id)
        if application is None or application.organization_id != organization_id:
            raise NotFoundError("JobApplication was not found.")

        # Stage G Advance Gate
        InterviewService._check_advance_gate(db, application)

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        invitation = CandidateInvitation(
            organization_id=organization_id,
            job_application_id=job_application_id,
            token=token,
            expires_at=expires_at,
            status="pending",
            notes=notes,
        )
        db.add(invitation)
        db.flush()

        AuditService().log_event(
            db,
            action="candidate_invitation.created",
            entity_type="candidate_invitation",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            entity_id=invitation.id,
            metadata={
                "job_application_id": str(job_application_id),
                "expires_at": expires_at.isoformat(),
            },
            flush=False,
        )
        return invitation

    def get_invitation_by_token(
        self,
        db: Session,
        token: str,
    ) -> CandidateInvitation:
        """Resolve and validate an invitation token from the candidate perspective."""
        invitation = db.scalar(
            select(CandidateInvitation).where(CandidateInvitation.token == token)
        )
        if invitation is None:
            raise NotFoundError("Invitation token is invalid or does not exist.")

        if invitation.status == "cancelled":
            raise ValidationError("This interview invitation has been cancelled.")

        # Ensure timezone-aware comparison
        now = datetime.now(timezone.utc)
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            if invitation.status != "expired":
                invitation.status = "expired"
                db.flush()
            raise ValidationError("This interview invitation has expired.")

        # Enforce that application decision still permits scheduling (Stage G)
        application = invitation.job_application
        InterviewService._check_advance_gate(db, application)

        return invitation

    def get_candidate_view(
        self,
        db: Session,
        token: str,
    ) -> dict[str, Any]:
        """Return candidate-safe details. Strictly redacts internal scores and notes."""
        invitation = self.get_invitation_by_token(db, token)
        application = invitation.job_application
        candidate = application.candidate
        job = application.job

        return {
            "invitation_id": invitation.id,
            "status": invitation.status,
            "expires_at": invitation.expires_at,
            "notes": invitation.notes,
            "candidate_name": candidate.full_name,
            "job_title": job.title,
            "department": job.department,
            "location": job.location,
            "employment_type": job.job_type,
        }

    def list_available_slots_for_invitation(
        self,
        db: Session,
        token: str,
        scheduled_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Return genuinely open slots for this invitation without conflicts."""
        invitation = self.get_invitation_by_token(db, token)
        application = invitation.job_application

        # Find published availabilities in the org
        availabilities = self.list_availability(
            db,
            organization_id=invitation.organization_id,
            scheduled_date=scheduled_date,
        )

        open_slots: list[dict[str, Any]] = []
        for avail in availabilities:
            interviewer = avail.interviewer
            start_min = _to_minutes(avail.start_time)
            end_min = _to_minutes(avail.end_time)
            slot_duration = avail.duration_minutes

            # Slide by slot duration through the available block
            current = start_min
            while current + slot_duration <= end_min:
                conflicts = InterviewService().find_conflicts(
                    db,
                    organization_id=invitation.organization_id,
                    job_application_id=application.id,
                    candidate_id=application.candidate_id,
                    interviewer_user_id=interviewer.id,
                    scheduled_date=avail.scheduled_date,
                    start_minutes=current,
                    duration_minutes=slot_duration,
                )
                if not conflicts:
                    open_slots.append(
                        {
                            "availability_id": avail.id,
                            "interviewer_id": interviewer.id,
                            "interviewer_name": interviewer.full_name,
                            "date": avail.scheduled_date.isoformat(),
                            "start_time": _to_hhmm(current),
                            "end_time": _to_hhmm(current + slot_duration),
                            "duration_minutes": slot_duration,
                            "timezone": avail.timezone,
                        }
                    )
                current += slot_duration

        return open_slots

    def candidate_book_slot(
        self,
        db: Session,
        *,
        token: str,
        scheduled_date: date,
        scheduled_time: str,
        duration_minutes: int = DEFAULT_DURATION_MINUTES,
        interviewer_user_id: uuid.UUID | None = None,
    ) -> Interview:
        """Candidate selects an open slot.

        Protected by database row locking to prevent concurrent double-booking.
        """
        invitation = self.get_invitation_by_token(db, token)
        if invitation.status == "booked":
            raise ValidationError("This invitation has already been used to book an interview.")

        application = invitation.job_application

        # Prevent past-date bookings
        if scheduled_date < date.today():
            raise ValidationError("Cannot book an interview slot in the past.")

        interview = InterviewService().schedule(
            db,
            organization_id=invitation.organization_id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            interview_type="technical",
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            interviewer_user_id=interviewer_user_id,
            scheduled_duration_minutes=duration_minutes,
            meeting_link="https://meet.hera-recruitment.internal/" + secrets.token_hex(6),
        )

        invitation.status = "booked"
        db.flush()

        AuditService().log_event(
            db,
            action="candidate_invitation.booked",
            entity_type="candidate_invitation",
            organization_id=invitation.organization_id,
            actor_user_id=None,
            entity_id=invitation.id,
            metadata={
                "interview_id": str(interview.id),
                "scheduled_date": scheduled_date.isoformat(),
                "scheduled_time": scheduled_time,
            },
            flush=False,
        )
        return interview

    def candidate_cancel_booking(
        self,
        db: Session,
        *,
        token: str,
        interview_id: uuid.UUID,
    ) -> Interview:
        """Safely allow candidate to cancel an appointment."""
        invitation = self.get_invitation_by_token(db, token)
        application = invitation.job_application

        interview = db.get(Interview, interview_id)
        if (
            interview is None
            or interview.job_application_id != application.id
            or interview.organization_id != invitation.organization_id
        ):
            raise NotFoundError("Interview was not found for this invitation.")

        cancelled = InterviewService().cancel(
            db,
            interview_id=interview_id,
            organization_id=invitation.organization_id,
        )
        invitation.status = "pending"  # Re-enable invitation for re-booking
        db.flush()

        AuditService().log_event(
            db,
            action="candidate_invitation.booking_cancelled",
            entity_type="candidate_invitation",
            organization_id=invitation.organization_id,
            actor_user_id=None,
            entity_id=invitation.id,
            metadata={"interview_id": str(interview.id)},
            flush=False,
        )
        return cancelled
