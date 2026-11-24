from __future__ import annotations

import hashlib
import logging
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
    InterviewSlotReservation,
    JobApplication,
    Organization,
    User,
)
from app.services.audit_service import AuditService
from app.services.email_outbox_service import EmailOutboxService
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.google_calendar_service import GoogleCalendarService
from app.services.interview_service import (
    DEFAULT_DURATION_MINUTES,
    InterviewService,
    _to_hhmm,
    _to_minutes,
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CandidateInvitationIssue:
    invitation: CandidateInvitation
    token: str


class SchedulingWorkflowService:
    """Manages interviewer availability, candidate invitations, and candidate self-scheduling."""

    def __init__(self, now_fn=None):
        self._now_fn = now_fn or datetime.now

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

        if scheduled_date < self._now_fn(timezone_info).date():
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
        expires_at = self._now_fn(timezone.utc) + timedelta(days=expires_in_days)

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

        candidate_email = application.candidate.email
        if candidate_email:
            EmailOutboxService().enqueue(
                db,
                organization_id=organization_id,
                recipient=candidate_email,
                subject=f"Interview scheduling invitation: {application.job.title}",
                template="candidate_interview_invitation",
                payload={
                    "job_application_id": str(job_application_id),
                    "invitation_id": str(invitation.id),
                    "expires_at": expires_at.isoformat(),
                },
            )

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
        now = self._now_fn(timezone.utc)
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # Initial invitation expiry remains 7 days. After booking, the same token may be
        # used for eligible future rescheduling of that booked interview.
        if invitation.status == "pending" and now > expires_at:
            invitation.status = "expired"
            db.flush()
            raise ValidationError("This interview invitation has expired.")
        if invitation.status == "expired":
            raise ValidationError("This interview invitation has expired.")

        # Enforce that application decision still permits scheduling/rescheduling (Stage G)
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
            "interview_id": invitation.booked_interview_id,
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
            "can_reschedule": self._eligible_for_reschedule(invitation),
        }

    def _eligible_for_reschedule(self, invitation: CandidateInvitation) -> bool:
        if invitation.status != "booked" or invitation.booked_interview is None:
            return False
        interview = invitation.booked_interview
        if interview.status != "scheduled":
            return False
        # eligible only for future interviews
        now = self._now_fn(timezone.utc)
        start_at = interview.scheduled_start_at
        if start_at is None:
            return False
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
        return start_at > now

    def list_available_slots_for_invitation(
        self,
        db: Session,
        token: str,
        month: date,
    ) -> list[dict[str, Any]]:
        """Return genuinely open slots for this invitation without conflicts."""
        invitation = self.get_invitation_by_token(db, token)
        rescheduling = self._eligible_for_reschedule(invitation)
        if invitation.status == "booked" and not rescheduling:
            return []
        if invitation.status not in {"pending", "booked"}:
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

        exclude_interview_id = invitation.booked_interview_id if rescheduling else None
        open_slots: list[dict[str, Any]] = []
        for avail in availabilities:
            interviewer = avail.interviewer
            start_min = _to_minutes(avail.start_time)
            end_min = _to_minutes(avail.end_time)
            slot_duration = avail.duration_minutes
            timezone_info = ZoneInfo(avail.timezone)
            local_now = self._now_fn(timezone_info)

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
                    exclude_interview_id=exclude_interview_id,
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
                            "start_at": slot_datetime.astimezone(timezone.utc),
                        }
                    )
                current += slot_duration

        return open_slots

    def _enqueue_calendar_upsert(self, db: Session, interview: Interview, *, timezone_name: str, hr_user_id: uuid.UUID | None) -> None:
        from app.services.calendar_outbox_service import CalendarOutboxService

        CalendarOutboxService().enqueue(
            db,
            organization_id=interview.organization_id,
            interview_id=interview.id,
            hr_user_id=hr_user_id,
            operation="upsert_interview",
            idempotency_key=f"interview:{interview.id}:upsert:{interview.scheduled_start_at.isoformat()}",
            payload={
                "interview_id": str(interview.id),
                "hr_user_id": str(hr_user_id) if hr_user_id else None,
                "timezone": timezone_name,
            },
        )

    def _enqueue_calendar_cancel(self, db: Session, interview: Interview, *, hr_user_id: uuid.UUID | None) -> None:
        if not interview.google_event_id:
            return
        from app.services.calendar_outbox_service import CalendarOutboxService

        CalendarOutboxService().enqueue(
            db,
            organization_id=interview.organization_id,
            interview_id=interview.id,
            hr_user_id=hr_user_id,
            operation="cancel_event",
            idempotency_key=f"interview:{interview.id}:cancel:{interview.google_event_id}",
            payload={
                "interview_id": str(interview.id),
                "hr_user_id": str(hr_user_id) if hr_user_id else None,
                "calendar_id": interview.google_calendar_id or "primary",
                "event_id": interview.google_event_id,
            },
        )

    def _validate_slot_request(self, availability: InterviewAvailability, scheduled_time: str) -> tuple[int, datetime, datetime]:
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
        if requested_local <= self._now_fn(timezone_info):
            raise ValidationError("Cannot book an interview slot in the past.")
        return requested, requested_local, requested_local + timedelta(minutes=duration_minutes)

    def candidate_book_slot(
        self,
        db: Session,
        *,
        token: str,
        availability_id: uuid.UUID,
        scheduled_time: str,
    ) -> Interview:
        """Candidate books or atomically reschedules an interview.

        DB transaction + reservation constraints enforce overlap protection; calendar/email
        side effects are durably outboxed for async processing/reconciliation.
        """
        from sqlalchemy.exc import IntegrityError
        from app.models import InterviewSlotReservation

        invitation = self.get_invitation_by_token(db, token)
        rescheduling = self._eligible_for_reschedule(invitation)
        if invitation.status == "booked" and not rescheduling:
            raise ValidationError("This interview can no longer be rescheduled.")
        if invitation.status not in {"pending", "booked"}:
            raise ValidationError("This invitation cannot be used to book an interview.")

        application = db.scalar(
            select(JobApplication)
            .where(JobApplication.id == invitation.job_application_id)
            .with_for_update()
        )
        if application is None:
            raise NotFoundError("JobApplication was not found.")

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

        _, requested_local, slot_end_dt = self._validate_slot_request(availability, scheduled_time)

        # Ensure interviewer is ready in selected mode (prod requires valid connection)
        conn = GoogleCalendarService().ensure_hr_ready(
            db, organization_id=invitation.organization_id, interviewer_user_id=availability.interviewer_user_id
        )
        if not GoogleCalendarService().check_freebusy(
            db,
            conn,
            start=requested_local,
            end=slot_end_dt,
            calendar_id=(conn.calendar_id if conn else "primary"),
        ):
            raise ConflictError("Selected time is not available on the interviewer's Google Calendar.")

        # Acquire DB locks on relevant scheduled interviews for safety (reservation constraint is the source of truth)
        _ = list(
            db.scalars(
                select(Interview)
                .where(
                    Interview.organization_id == invitation.organization_id,
                    Interview.status == "scheduled",
                    Interview.scheduled_date == availability.scheduled_date,
                )
                .with_for_update()
            )
        )

        if rescheduling and invitation.booked_interview is not None:
            interview = db.scalar(
                select(Interview)
                .where(Interview.id == invitation.booked_interview_id)
                .with_for_update()
            )
            if interview is None or interview.status != "scheduled":
                raise ValidationError("This interview can no longer be rescheduled.")

            # Preserve same interview ID; update atomically in DB transaction.
            previous_hr_user_id = interview.interviewer_user_id
            previous_calendar_id = interview.google_calendar_id
            previous_event_id = interview.google_event_id
            interviewer_changed = previous_hr_user_id != availability.interviewer_user_id

            old_reservation = db.scalar(
                select(InterviewSlotReservation)
                .where(
                    InterviewSlotReservation.interview_id == interview.id,
                    InterviewSlotReservation.status == "active",
                )
                .with_for_update()
            )

            # Reserve the replacement slot first. If this flush conflicts, the
            # transaction rolls back while the old reservation/booking remain intact.
            replacement_start_at = requested_local.astimezone(ZoneInfo("UTC"))
            replacement_end_at = slot_end_dt.astimezone(ZoneInfo("UTC"))
            db.add(
                InterviewSlotReservation(
                    organization_id=invitation.organization_id,
                    interview_id=interview.id,
                    candidate_id=application.candidate_id,
                    interviewer_user_id=availability.interviewer_user_id,
                    scheduled_start_at=replacement_start_at,
                    scheduled_end_at=replacement_end_at,
                    status="active",
                )
            )
            try:
                db.flush()
            except IntegrityError as exc:
                raise ConflictError("Selected time is no longer available.") from exc

            if old_reservation is not None:
                old_reservation.status = "released"

            interview.interviewer_user_id = availability.interviewer_user_id
            interview.scheduled_date = availability.scheduled_date
            interview.scheduled_time = scheduled_time
            interview.scheduled_duration_minutes = availability.duration_minutes
            interview.scheduled_start_at = replacement_start_at
            interview.scheduled_end_at = replacement_end_at
            interview.calendar_sync_status = "pending"
            interview.calendar_sync_error = None

            # If the interviewer/calendar context changes, cancel the old calendar event (if any)
            # and create a fresh event for the new interviewer to avoid orphaned/incorrect events.
            if interviewer_changed and previous_event_id:
                self._enqueue_calendar_cancel(
                    db,
                    Interview(
                        id=interview.id,
                        organization_id=interview.organization_id,
                        interviewer_user_id=previous_hr_user_id,
                        google_calendar_id=previous_calendar_id or "primary",
                        google_event_id=previous_event_id,
                    ),
                    hr_user_id=previous_hr_user_id,
                )
                interview.google_event_id = None
                interview.google_calendar_id = None

            invitation.booked_availability_id = availability.id
            invitation.reschedule_count = (invitation.reschedule_count or 0) + 1
            invitation.last_rescheduled_at = self._now_fn(timezone.utc)

            # Durable, idempotent calendar update for same interview/event; if it fails later, outbox retries.
            self._enqueue_calendar_upsert(
                db, interview, timezone_name=availability.timezone, hr_user_id=availability.interviewer_user_id
            )

            if application.candidate.email:
                EmailOutboxService().enqueue(
                    db,
                    organization_id=invitation.organization_id,
                    recipient=application.candidate.email,
                    subject=f"Interview rescheduled: {application.job.title}",
                    template="candidate_interview_rescheduled",
                    payload={
                        "interview_id": str(interview.id),
                        "job_application_id": str(application.id),
                        "scheduled_date": availability.scheduled_date.isoformat(),
                    },
                )
            AuditService().log_event(
                db,
                action="candidate_invitation.rescheduled",
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
            db.flush()
            interview.rescheduled_via_invite = True  # type: ignore[attr-defined]
            return interview

        try:
            interview = InterviewService(now_fn=self._now_fn).schedule(
                db,
                organization_id=invitation.organization_id,
                candidate_id=application.candidate_id,
                job_id=application.job_id,
                interview_type="technical",
                scheduled_date=availability.scheduled_date,
                scheduled_time=scheduled_time,
                interviewer_user_id=availability.interviewer_user_id,
                scheduled_duration_minutes=availability.duration_minutes,
                meeting_link="https://meet.hera-recruitment.internal/" + secrets.token_hex(6),
                timezone_name=availability.timezone,
                calendar_prechecked=True,
            )
        except IntegrityError as exc:
            raise ConflictError("Selected time is no longer available.") from exc

        interview.calendar_sync_status = "pending"
        invitation.status = "booked"
        invitation.booked_interview_id = interview.id
        invitation.booked_availability_id = availability.id

        self._enqueue_calendar_upsert(
            db, interview, timezone_name=availability.timezone, hr_user_id=availability.interviewer_user_id
        )

        if application.candidate.email:
            EmailOutboxService().enqueue(
                db,
                organization_id=invitation.organization_id,
                recipient=application.candidate.email,
                subject=f"Interview booked: {application.job.title}",
                template="candidate_interview_booked",
                payload={
                    "interview_id": str(interview.id),
                    "job_application_id": str(application.id),
                    "scheduled_date": availability.scheduled_date.isoformat(),
                },
            )
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
        db.flush()
        interview.rescheduled_via_invite = False  # type: ignore[attr-defined]
        return interview

    def candidate_reschedule(
        self,
        db: Session,
        *,
        token: str,
        interview_id: uuid.UUID,
        availability_id: uuid.UUID,
        scheduled_time: str,
    ) -> Interview:
        invitation = self.get_invitation_by_token(db, token)
        if invitation.booked_interview_id != interview_id:
            raise ValidationError("This interview cannot be rescheduled with this link.")
        return self.candidate_book_slot(
            db, token=token, availability_id=availability_id, scheduled_time=scheduled_time
        )
