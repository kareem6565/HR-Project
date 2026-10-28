from __future__ import annotations

import hashlib
import secrets
import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


@dataclass(frozen=True)
class CandidateInvitationIssue:
    invitation: CandidateInvitation
    token: str


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

        try:
            timezone_info = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            raise ValidationError("timezone must be a valid IANA time zone.") from None

        if scheduled_date < datetime.now(timezone_info).date():
            raise ValidationError("Availability cannot be published for a past date.")

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

    def cancel_availability(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        availability_id: uuid.UUID,
    ) -> InterviewAvailability:
        availability = db.scalar(
            select(InterviewAvailability)
            .where(
                InterviewAvailability.id == availability_id,
                InterviewAvailability.organization_id == organization_id,
            )
            .with_for_update()
        )
        if availability is None:
            raise NotFoundError("Availability was not found.")
        if availability.status != "available":
            raise ValidationError("Only published availability can be withdrawn.")
        availability.status = "cancelled"
        db.flush()
        return availability

    def list_availability(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        scheduled_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
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
        if start_date is not None:
            stmt = stmt.where(InterviewAvailability.scheduled_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(InterviewAvailability.scheduled_date <= end_date)
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
    ) -> CandidateInvitationIssue:
        """Issue a secure, candidate-facing interview invitation token.

        Enforces Stage G: Advance Gate — candidates cannot be invited for interviews
        unless HR has made an authoritative 'advance' decision.
        """
        application = db.scalar(
            select(JobApplication)
            .where(
                JobApplication.id == job_application_id,
                JobApplication.organization_id == organization_id,
            )
            .with_for_update()
        )
        if application is None:
            raise NotFoundError("JobApplication was not found.")
        if expires_in_days != 7:
            raise ValidationError("Interview invitation links expire after exactly 7 days.")

        # Stage G Advance Gate
        InterviewService._check_advance_gate(db, application)

        already_scheduled = db.scalar(
            select(Interview.id)
            .join(
                CandidateInvitation,
                CandidateInvitation.booked_interview_id == Interview.id,
            )
            .where(
                CandidateInvitation.organization_id == organization_id,
                CandidateInvitation.job_application_id == job_application_id,
                CandidateInvitation.status == "booked",
                Interview.status == "scheduled",
            )
        )
        if already_scheduled is not None:
            raise ConflictError(
                "An interview is already scheduled for this application. "
                "Cancel it before issuing a replacement link."
            )

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Keep only one live invitation per application. Reissuing invalidates
        # older unused links, while booked interviews remain untouched.
        pending = db.scalars(
            select(CandidateInvitation)
            .where(
                CandidateInvitation.organization_id == organization_id,
                CandidateInvitation.job_application_id == job_application_id,
                CandidateInvitation.status == "pending",
            )
            .with_for_update()
        )
        for prior in pending:
            prior.status = "cancelled"

        invitation = CandidateInvitation(
            organization_id=organization_id,
            job_application_id=job_application_id,
            token_hash=token_hash,
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
        return CandidateInvitationIssue(invitation=invitation, token=token)

    def get_invitation_by_token(
        self,
        db: Session,
        token: str,
    ) -> CandidateInvitation:
        """Resolve and validate an invitation token from the candidate perspective."""
        invitation = db.scalar(
            select(CandidateInvitation)
            .where(
                CandidateInvitation.token_hash
                == hashlib.sha256(token.encode("utf-8")).hexdigest()
            )
            .with_for_update()
        )
        if invitation is None:
            raise NotFoundError("Invitation token is invalid or does not exist.")

        if invitation.status == "cancelled":
            raise ValidationError("This interview invitation is no longer active.")

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
            "status": invitation.status,
            "expires_at": invitation.expires_at,
            "candidate_name": candidate.full_name,
            "job_title": job.title,
            "department": job.department,
            "location": job.location,
            "employment_type": job.job_type,
            "scheduled_date": (
                invitation.booked_interview.scheduled_date.isoformat()
                if invitation.booked_interview is not None
                else None
            ),
            "scheduled_time": (
                invitation.booked_interview.scheduled_time
                if invitation.booked_interview is not None
                else None
            ),
            "scheduled_duration_minutes": (
                invitation.booked_interview.scheduled_duration_minutes
                if invitation.booked_interview is not None
                else None
            ),
            "timezone": (
                invitation.booked_availability.timezone
                if invitation.booked_availability is not None
                else None
            ),
        }

    def list_available_slots_for_invitation(
        self,
        db: Session,
        token: str,
        month: date,
    ) -> list[dict[str, Any]]:
        """Return genuinely open slots for this invitation without conflicts."""
        invitation = self.get_invitation_by_token(db, token)
        if invitation.status != "pending":
            return []
        application = invitation.job_application

        # Find published availabilities in the org
        availabilities = self.list_availability(
            db,
            organization_id=invitation.organization_id,
        )

        month_end = month.replace(day=monthrange(month.year, month.month)[1])
        availabilities = [
            availability
            for availability in availabilities
            if month <= availability.scheduled_date <= month_end
        ]

        open_slots: list[dict[str, Any]] = []
        for avail in availabilities:
            interviewer = avail.interviewer
            start_min = _to_minutes(avail.start_time)
            end_min = _to_minutes(avail.end_time)
            slot_duration = avail.duration_minutes
            timezone_info = ZoneInfo(avail.timezone)
            local_now = datetime.now(timezone_info)

            # Slide by slot duration through the available block
            current = start_min
            while current + slot_duration <= end_min:
                slot_datetime = datetime.combine(
                    avail.scheduled_date,
                    time(hour=current // 60, minute=current % 60),
                    tzinfo=timezone_info,
                )
                if slot_datetime <= local_now:
                    current += slot_duration
                    continue
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
        availability_id: uuid.UUID,
        scheduled_time: str,
    ) -> Interview:
        """Candidate selects an open slot.

        Protected by database row locking to prevent concurrent double-booking.
        """
        invitation = self.get_invitation_by_token(db, token)
        if invitation.status == "booked":
            raise ValidationError("This invitation has already been used to book an interview.")

        application = invitation.job_application

        availability = db.scalar(
            select(InterviewAvailability)
            .where(
                InterviewAvailability.id == availability_id,
                InterviewAvailability.organization_id == invitation.organization_id,
                InterviewAvailability.status == "available",
            )
            .with_for_update()
        )
        if availability is None:
            raise ValidationError("This availability is no longer open.")

        start = _to_minutes(availability.start_time)
        end = _to_minutes(availability.end_time)
        requested = _to_minutes(scheduled_time)
        duration_minutes = availability.duration_minutes
        if (
            requested < start
            or requested + duration_minutes > end
            or (requested - start) % duration_minutes != 0
        ):
            raise ValidationError("Choose an interview time shown as available.")

        timezone_info = ZoneInfo(availability.timezone)
        requested_local = datetime.combine(
            availability.scheduled_date,
            time(hour=requested // 60, minute=requested % 60),
            tzinfo=timezone_info,
        )
        if requested_local <= datetime.now(timezone_info):
            raise ValidationError("Cannot book an interview slot in the past.")
        if invitation.job_application_id != application.id:
            raise ValidationError("This invitation is not valid for this application.")

        interview = InterviewService().schedule(
            db,
            organization_id=invitation.organization_id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            interview_type="technical",
            scheduled_date=availability.scheduled_date,
            scheduled_time=scheduled_time,
            interviewer_user_id=availability.interviewer_user_id,
            scheduled_duration_minutes=duration_minutes,
            meeting_link="https://meet.hera-recruitment.internal/" + secrets.token_hex(6),
        )

        invitation.status = "booked"
        invitation.booked_interview_id = interview.id
        invitation.booked_availability_id = availability.id
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
                "scheduled_date": availability.scheduled_date.isoformat(),
                "scheduled_time": scheduled_time,
            },
            flush=False,
        )
        return interview
