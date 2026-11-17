from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import (
    Candidate,
    CandidateInvitation,
    HRDecision,
    Interview,
    InterviewAvailability,
    Job,
    JobApplication,
    Organization,
    Resume,
    User,
)
from app.services.errors import ValidationError
from app.services.interview_service import InterviewService
from app.services.scheduling_workflow_service import SchedulingWorkflowService


def _seed_advanced_application(
    db,
    *,
    window_start="11:00",
    window_end="13:00",
    duration_minutes=30,
    scheduled_date=None,
    timezone="UTC",
):
    org = Organization(id=uuid.uuid4(), name="Avail Org", status="active")
    interviewer = User(
        id=uuid.uuid4(),
        organization_id=org.id,
        email=f"hr-{uuid.uuid4().hex}@example.com",
        full_name="HR Interviewer",
        role="recruiter",
        roles=["recruiter"],
        status="active",
        is_active=True,
    )
    candidate = Candidate(
        id=uuid.uuid4(),
        organization_id=org.id,
        full_name="Candidate One",
        email=f"cand-{uuid.uuid4().hex}@example.com",
        status="active",
    )
    job = Job(id=uuid.uuid4(), organization_id=org.id, title="Engineer")
    resume = Resume(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        file_uri="file://test/resume.pdf",
        original_filename="resume.pdf",
        status="uploaded",
    )
    db.add_all([org, interviewer, candidate, job, resume])
    db.flush()
    app = JobApplication(
        id=uuid.uuid4(),
        organization_id=org.id,
        candidate_id=candidate.id,
        job_id=job.id,
        resume_id=resume.id,
        status="advanced",
    )
    db.add(app)
    db.flush()
    db.add(HRDecision(id=uuid.uuid4(), job_application_id=app.id, user_id=interviewer.id, decision="advance"))
    avail = InterviewAvailability(
        id=uuid.uuid4(),
        organization_id=org.id,
        interviewer_user_id=interviewer.id,
        scheduled_date=scheduled_date or date.today() + timedelta(days=3),
        start_time=window_start,
        end_time=window_end,
        duration_minutes=duration_minutes,
        timezone=timezone,
        status="available",
    )
    db.add(avail)
    db.flush()
    return org, interviewer, candidate, job, app, avail


def test_cairo_boundary_uses_injected_absolute_clock_for_hr_and_candidate(db_session):
    fixed_utc = datetime(2026, 11, 12, 15, 54, tzinfo=timezone.utc)
    now_fn = lambda tz: fixed_utc.astimezone(tz)
    org, interviewer, candidate, job, app, avail = _seed_advanced_application(
        db_session,
        window_start="17:24",
        window_end="19:00",
        scheduled_date=date(2026, 11, 12),
        timezone="Africa/Cairo",
    )

    with pytest.raises(ValidationError, match="past"):
        InterviewService(now_fn=now_fn).schedule(
            db_session,
            organization_id=org.id,
            candidate_id=candidate.id,
            job_id=job.id,
            interview_type="technical",
            scheduled_date=avail.scheduled_date,
            scheduled_time="17:54",
            interviewer_user_id=interviewer.id,
            scheduled_duration_minutes=30,
        )

    issue = SchedulingWorkflowService(now_fn=now_fn).create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=app.id,
        actor_user_id=interviewer.id,
    )
    with pytest.raises(ValidationError, match="past"):
        SchedulingWorkflowService(now_fn=now_fn).candidate_book_slot(
            db_session,
            token=issue.token,
            availability_id=avail.id,
            scheduled_time="17:54",
        )


class TestHRInterviewSchedulingAvailabilityWindow:
    def test_accepts_interview_at_12_00_for_30_minutes(self, db_session):
        org, interviewer, candidate, job, app, avail = _seed_advanced_application(db_session)
        interview = InterviewService().schedule(
            db_session,
            organization_id=org.id,
            candidate_id=candidate.id,
            job_id=job.id,
            interview_type="technical",
            scheduled_date=avail.scheduled_date,
            scheduled_time="12:00",
            interviewer_user_id=interviewer.id,
            scheduled_duration_minutes=30,
        )
        db_session.flush()
        assert interview.status == "scheduled"
        assert interview.scheduled_time == "12:00"
        assert interview.scheduled_duration_minutes == 30

    def test_rejects_interview_at_14_00_outside_window(self, db_session):
        org, interviewer, candidate, job, app, avail = _seed_advanced_application(db_session)
        with pytest.raises(ValidationError, match="outside the interviewer's published availability"):
            InterviewService().schedule(
                db_session,
                organization_id=org.id,
                candidate_id=candidate.id,
                job_id=job.id,
                interview_type="technical",
                scheduled_date=avail.scheduled_date,
                scheduled_time="14:00",
                interviewer_user_id=interviewer.id,
                scheduled_duration_minutes=30,
            )

    def test_rejects_interview_ending_after_window(self, db_session):
        org, interviewer, candidate, job, app, avail = _seed_advanced_application(db_session)
        with pytest.raises(ValidationError, match="outside the interviewer's published availability"):
            InterviewService().schedule(
                db_session,
                organization_id=org.id,
                candidate_id=candidate.id,
                job_id=job.id,
                interview_type="technical",
                scheduled_date=avail.scheduled_date,
                scheduled_time="12:45",
                interviewer_user_id=interviewer.id,
                scheduled_duration_minutes=30,
            )

    def test_accepts_interview_ending_exactly_at_window_end(self, db_session):
        org, interviewer, candidate, job, app, avail = _seed_advanced_application(db_session)
        interview = InterviewService().schedule(
            db_session,
            organization_id=org.id,
            candidate_id=candidate.id,
            job_id=job.id,
            interview_type="technical",
            scheduled_date=avail.scheduled_date,
            scheduled_time="12:30",
            interviewer_user_id=interviewer.id,
            scheduled_duration_minutes=30,
        )
        db_session.flush()
        assert interview.scheduled_time == "12:30"
        assert interview.scheduled_duration_minutes == 30


class TestCandidateBookingReschedulingAvailabilityWindow:
    def test_candidate_booking_rejects_time_outside_window(self, db_session):
        org, interviewer, _candidate, _job, app, avail = _seed_advanced_application(db_session)
        issue = SchedulingWorkflowService().create_invitation(
            db_session, organization_id=org.id, job_application_id=app.id, actor_user_id=interviewer.id, expires_in_days=7
        )
        db_session.flush()
        with pytest.raises(ValidationError, match="Choose an interview time shown as available"):
            SchedulingWorkflowService().candidate_book_slot(
                db_session, token=issue.token, availability_id=avail.id, scheduled_time="14:00"
            )

    def test_candidate_booking_accepts_ending_exactly_at_window_end(self, db_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "google_calendar_mode", "hera")
        org, interviewer, _candidate, _job, app, avail = _seed_advanced_application(db_session)
        issue = SchedulingWorkflowService().create_invitation(
            db_session, organization_id=org.id, job_application_id=app.id, actor_user_id=interviewer.id, expires_in_days=7
        )
        db_session.flush()
        interview = SchedulingWorkflowService().candidate_book_slot(
            db_session, token=issue.token, availability_id=avail.id, scheduled_time="12:30"
        )
        db_session.flush()
        assert interview.scheduled_time == "12:30"
        assert interview.scheduled_duration_minutes == 30

    def test_candidate_reschedule_rejects_outside_window(self, db_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "google_calendar_mode", "hera")
        org, interviewer, _candidate, _job, app, avail = _seed_advanced_application(db_session)
        # add second valid slot block later for valid initial booking? use 11:00 then try reschedule to 14:00
        avail2 = InterviewAvailability(
            id=uuid.uuid4(),
            organization_id=org.id,
            interviewer_user_id=interviewer.id,
            scheduled_date=avail.scheduled_date,
            start_time="14:00",
            end_time="15:00",
            duration_minutes=30,
            timezone="UTC",
            status="available",
        )
        db_session.add(avail2)
        db_session.flush()

        issue = SchedulingWorkflowService().create_invitation(
            db_session, organization_id=org.id, job_application_id=app.id, actor_user_id=interviewer.id, expires_in_days=7
        )
        interview = SchedulingWorkflowService().candidate_book_slot(
            db_session, token=issue.token, availability_id=avail.id, scheduled_time="11:00"
        )
        db_session.flush()
        assert interview.scheduled_time == "11:00"

        # Attempt reschedule to a time outside avail (11:00-13:00 window) via same availability
        with pytest.raises(ValidationError, match="Choose an interview time shown as available"):
            SchedulingWorkflowService().candidate_reschedule(
                db_session,
                token=issue.token,
                interview_id=interview.id,
                availability_id=avail.id,
                scheduled_time="14:00",
            )

        # Reschedule to valid time inside window succeeds
        rescheduled = SchedulingWorkflowService().candidate_reschedule(
            db_session,
            token=issue.token,
            interview_id=interview.id,
            availability_id=avail.id,
            scheduled_time="12:00",
        )
        db_session.flush()
        assert rescheduled.id == interview.id
        assert rescheduled.scheduled_time == "12:00"
