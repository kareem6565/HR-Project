from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    Interview,
    Job,
    JobApplication,
    Organization,
    User,
)
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.user_service import UserService

_TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?$")

DEFAULT_DURATION_MINUTES = 60


class InterviewService:
    """Org-scoped scheduling, cancellation, and feedback for interviews.

    An interview is always attached to a real JobApplication (candidate + job)
    so it stays grounded in the recruitment pipeline.
    """

    def schedule(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        interview_type: str,
        scheduled_date,
        scheduled_time: str,
        interviewer_user_id: uuid.UUID | None,
        meeting_link: str | None = None,
        scheduled_duration_minutes: int = DEFAULT_DURATION_MINUTES,
        interview_question_set_id: uuid.UUID | None = None,
    ) -> Interview:
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization was not found.")
        application = self._resolve_application(
            db,
            organization_id=organization_id,
            candidate_id=candidate_id,
            job_id=job_id,
        )

        # Stage G: Enforce Advance Gate
        self._check_advance_gate(db, application)

        interviewer = None
        if interviewer_user_id is not None:
            interviewer = UserService().get(
                db,
                user_id=interviewer_user_id,
                organization_id=organization_id,
            )
        self._validate_schedule(
            interview_type,
            scheduled_date,
            scheduled_time,
            scheduled_duration_minutes,
        )
        question_set = None
        if interview_question_set_id is not None:
            from app.services.interview_question_service import InterviewQuestionService

            candidate_set = InterviewQuestionService().get(
                db,
                question_set_id=interview_question_set_id,
                organization_id=organization_id,
            )
            if candidate_set.job_application_id != application.id:
                raise ValidationError(
                    "Interview question set does not belong to this candidate's application."
                )
            if candidate_set.status != "approved":
                raise ValidationError(
                    "Only an approved interview question set can be attached to an interview."
                )
            question_set = candidate_set

        # Concurrency protection: lock application row to prevent race conditions
        db.scalars(
            select(JobApplication)
            .where(JobApplication.id == application.id)
            .with_for_update()
        ).first()

        interval = _to_minutes(scheduled_time)
        conflicts = self.find_conflicts(
            db,
            organization_id=organization_id,
            job_application_id=application.id,
            candidate_id=application.candidate_id,
            interviewer_user_id=interviewer.id if interviewer is not None else None,
            scheduled_date=scheduled_date,
            start_minutes=interval,
            duration_minutes=scheduled_duration_minutes,
        )
        if conflicts:
            requested_interviewer_id = interviewer.id if interviewer is not None else None
            raise ConflictError(
                _conflict_message(
                    conflicts[0],
                    requested_interviewer_user_id=requested_interviewer_id,
                    requested_candidate_id=application.candidate_id,
                )
            )

        interview = Interview(
            organization_id=organization_id,
            job_application_id=application.id,
            interviewer_user_id=interviewer.id if interviewer is not None else None,
            interview_question_set_id=question_set.id if question_set is not None else None,
            status="scheduled",
            interview_type=interview_type,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            scheduled_duration_minutes=scheduled_duration_minutes,
            meeting_link=meeting_link,
        )
        db.add(interview)
        db.flush()
        return interview

    def list(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        status: str | None = None,
    ) -> list[Interview]:
        """Return org interviews, newest first, optionally filtered by status."""
        statement = (
            select(Interview)
            .where(Interview.organization_id == organization_id)
            .order_by(Interview.scheduled_date.desc(), Interview.scheduled_time)
        )
        if status:
            normalized = status.strip().lower()
            if normalized not in {"scheduled", "completed", "cancelled"}:
                raise ValidationError("Interview status filter is not supported.")
            statement = statement.where(Interview.status == normalized)
        return list(db.scalars(statement))

    def get(
        self,
        db: Session,
        *,
        interview_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Interview:
        interview = db.get(Interview, interview_id)
        if interview is None or interview.organization_id != organization_id:
            raise NotFoundError("Interview was not found.")
        return interview

    def cancel(
        self,
        db: Session,
        *,
        interview_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Interview:
        interview = self.get(db, interview_id=interview_id, organization_id=organization_id)
        if interview.status == "cancelled":
            return interview
        if interview.status == "completed":
            raise ValidationError("A completed interview cannot be cancelled.")
        interview.status = "cancelled"
        db.flush()
        return interview

    def submit_feedback(
        self,
        db: Session,
        *,
        interview_id: uuid.UUID,
        organization_id: uuid.UUID,
        feedback: dict[str, Any],
        is_amendment: bool = False,
    ) -> Interview:
        interview = self.get(db, interview_id=interview_id, organization_id=organization_id)
        if interview.status == "cancelled":
            raise ValidationError("Feedback cannot be submitted for a cancelled interview.")
        if interview.feedback is not None and not is_amendment:
            raise ValidationError(
                "Feedback has already been submitted for this interview. "
                "Use an amendment to update submitted feedback."
            )

        # Validate rubric
        for field in ("technical", "communication", "problem_solving"):
            val = feedback.get(field)
            if val is None or not isinstance(val, (int, float)) or not (1 <= val <= 5):
                raise ValidationError(f"{field} rating must be between 1 and 5.")
        overall = feedback.get("overall")
        if overall is None or not (1.0 <= float(overall) <= 5.0):
            raise ValidationError("overall rating must be between 1.0 and 5.0.")

        feedback["submitted_at"] = datetime.now().date().isoformat()
        if is_amendment and interview.feedback:
            history = interview.feedback.get("_history", [])
            prev_copy = {k: v for k, v in interview.feedback.items() if k != "_history"}
            history.append(prev_copy)
            feedback["_history"] = history

        interview.feedback = feedback
        interview.status = "completed"
        db.flush()
        return interview

    @staticmethod
    def _check_advance_gate(db: Session, application: JobApplication) -> None:
        """Enforce that only candidates with an authoritative HR 'advance' decision can be scheduled."""
        from app.models.hr_decision import HRDecision

        latest_decision = db.scalars(
            select(HRDecision)
            .where(HRDecision.job_application_id == application.id)
            .order_by(HRDecision.created_at.desc(), HRDecision.id.desc())
            .limit(1)
        ).first()

        if application.status == "advanced" or (
            latest_decision is not None and latest_decision.decision == "advance"
        ):
            return

        decision_state = (
            latest_decision.decision
            if latest_decision is not None
            else application.status
        )
        raise ValidationError(
            f"Interview scheduling denied: Application status is {decision_state!r}. "
            "An authoritative HR 'advance' decision is required before scheduling an interview."
        )

    def list_interviewers(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
    ) -> list[User]:
        return UserService().list_org_users(db, organization_id=organization_id)

    @staticmethod
    def to_response(interview: Interview) -> dict[str, Any]:
        """Compose the read model with candidate/job/interviewer display data."""
        application = interview.job_application
        candidate = application.candidate
        job = application.job
        interviewer = interview.interviewer
        return {
            "id": interview.id,
            "organization_id": interview.organization_id,
            "job_application_id": interview.job_application_id,
            "interviewer_user_id": interview.interviewer_user_id,
            "interviewer_name": interviewer.full_name if interviewer is not None else None,
            "candidate_id": candidate.id,
            "candidate_name": candidate.full_name,
            "candidate_email": candidate.email,
            "job_id": job.id,
            "job_title": job.title,
            "interview_type": interview.interview_type,
            "status": interview.status,
            "scheduled_date": interview.scheduled_date,
            "scheduled_time": interview.scheduled_time,
            "scheduled_duration_minutes": interview.scheduled_duration_minutes,
            "interview_question_set_id": interview.interview_question_set_id,
            "meeting_link": interview.meeting_link,
            "feedback": interview.feedback,
            "created_at": interview.created_at,
        }

    @staticmethod
    def _resolve_application(
        db: Session,
        *,
        organization_id: uuid.UUID,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> JobApplication:
        candidate = db.get(Candidate, candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            raise NotFoundError("Candidate was not found.")
        job = db.get(Job, job_id)
        if job is None or job.organization_id != organization_id:
            raise NotFoundError("Job was not found.")
        statement = select(JobApplication).where(
            JobApplication.organization_id == organization_id,
            JobApplication.candidate_id == candidate_id,
            JobApplication.job_id == job_id,
        )
        application = db.scalar(statement)
        if application is None:
            raise ValidationError(
                "No application found for this candidate and job. "
                "Screen the candidate for the job before scheduling an interview."
            )
        return application

    @staticmethod
    def _validate_schedule(
        interview_type: str,
        scheduled_date,
        scheduled_time: str,
        scheduled_duration_minutes: int = DEFAULT_DURATION_MINUTES,
    ) -> None:
        if interview_type not in {"technical", "hr", "behavioral"}:
            raise ValidationError("Interview type must be technical, hr, or behavioral.")
        if not isinstance(scheduled_date, date):
            raise ValidationError("scheduled_date must be a valid date.")
        if not scheduled_time.strip():
            raise ValidationError("scheduled_time cannot be empty.")
        _to_minutes(scheduled_time)
        if not isinstance(scheduled_duration_minutes, int) or not (
            15 <= scheduled_duration_minutes <= 480
        ):
            raise ValidationError("scheduled_duration_minutes must be between 15 and 480.")

    def find_conflicts(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        job_application_id: uuid.UUID,
        candidate_id: uuid.UUID,
        interviewer_user_id: uuid.UUID | None,
        scheduled_date,
        start_minutes: int,
        duration_minutes: int,
    ) -> list[Interview]:
        """Return scheduled interviews overlapping the requested window.

        A conflict exists when another active (non-cancelled) interview in the
        same organization occupies an overlapping time window for the same
        interviewer OR for the same candidate, regardless of which job or
        application the interview belongs to. End-of-window is exclusive, so
        back-to-back interviews do not conflict.
        """
        end_minutes = start_minutes + duration_minutes
        statement = (
            select(Interview, JobApplication.candidate_id)
            .join(JobApplication, JobApplication.id == Interview.job_application_id)
            .where(
                Interview.organization_id == organization_id,
                Interview.status != "cancelled",
                Interview.scheduled_date == scheduled_date,
            )
        )
        conflicts: list[Interview] = []
        for existing, existing_candidate_id in db.execute(statement):
            existing_start = _to_minutes(existing.scheduled_time)
            existing_end = existing_start + (
                existing.scheduled_duration_minutes or DEFAULT_DURATION_MINUTES
            )
            overlaps = start_minutes < existing_end and existing_start < end_minutes
            same_interviewer = (
                interviewer_user_id is not None
                and existing.interviewer_user_id == interviewer_user_id
            )
            same_candidate = existing_candidate_id == candidate_id
            if overlaps and (same_interviewer or same_candidate):
                conflicts.append(existing)
        return conflicts

    def list_slots_for_date(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        scheduled_date,
        interviewer_user_id: uuid.UUID | None = None,
        duration_minutes: int = DEFAULT_DURATION_MINUTES,
    ) -> list[dict[str, Any]]:
        """Return occupied windows for the date in a compact, frontend-usable form."""
        if not isinstance(scheduled_date, date):
            raise ValidationError("scheduled_date must be a valid date.")
        statement = select(Interview).where(
            Interview.organization_id == organization_id,
            Interview.status != "cancelled",
            Interview.scheduled_date == scheduled_date,
        )
        occupied: list[dict[str, Any]] = []
        for existing in db.scalars(statement):
            if (
                interviewer_user_id is not None
                and existing.interviewer_user_id != interviewer_user_id
                and existing.job_application_id is not None
            ):
                continue
            start_minutes = _to_minutes(existing.scheduled_time)
            length = existing.scheduled_duration_minutes or DEFAULT_DURATION_MINUTES
            occupied.append(
                {
                    "interview_id": existing.id,
                    "interviewer_user_id": existing.interviewer_user_id,
                    "start_minutes": start_minutes,
                    "end_minutes": start_minutes + length,
                    "start_time": _to_hhmm(start_minutes),
                    "end_time": _to_hhmm(start_minutes + length),
                }
            )
        return occupied


def _to_hhmm(total_minutes: int) -> str:
    """Return ``HH:MM`` (24h) for a minutes-since-midnight value."""
    total_minutes %= 1440
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _to_minutes(scheduled_time: str) -> int:
    """Parse a HH:MM[ AM/PM] time into minutes since midnight.

    Accepts both 24-hour (``14:30``) and 12-hour (``2:30 PM``) forms. Raises a
    ``ValidationError`` for anything else.
    """
    match = _TIME_PATTERN.match(scheduled_time.strip())
    if match is None:
        raise ValidationError(
            f"scheduled_time {scheduled_time!r} is invalid; use HH:MM or HH:MM AM/PM."
        )
    hour = int(match.group(1))
    minute = int(match.group(2))
    period = (match.group(3) or "").upper()
    if minute >= 60:
        raise ValidationError("scheduled_time minute must be less than 60.")
    if period:
        if hour < 1 or hour > 12:
            raise ValidationError("scheduled_time hour must be 1-12 in AM/PM form.")
        if period == "PM" and hour != 12:
            hour += 12
        if period == "AM" and hour == 12:
            hour = 0
    else:
        if hour > 23:
            raise ValidationError("scheduled_time hour must be 0-23 in 24h form.")
    return hour * 60 + minute


def _conflict_message(
    interview: Interview,
    *,
    requested_interviewer_user_id: uuid.UUID | None,
    requested_candidate_id: uuid.UUID,
) -> str:
    """Compose a deterministic, descriptive 409 message for a schedule conflict."""
    same_interviewer = (
        requested_interviewer_user_id is not None
        and interview.interviewer_user_id == requested_interviewer_user_id
    )
    same_candidate = interview.job_application.candidate_id == requested_candidate_id
    if same_candidate and not same_interviewer:
        partner = f"candidate {interview.job_application.candidate.full_name}"
    else:
        partner = (
            interview.interviewer.full_name
            if interview.interviewer is not None
            else "the candidate"
        )
    duration = interview.scheduled_duration_minutes or DEFAULT_DURATION_MINUTES
    end_minutes = _to_minutes(interview.scheduled_time) + duration
    return (
        f"Schedule conflict: {partner} is already booked in another interview on "
        f"{interview.scheduled_date} ({_to_hhmm(_to_minutes(interview.scheduled_time))}–"
        f"{_to_hhmm(end_minutes)}). Choose another slot."
    )
