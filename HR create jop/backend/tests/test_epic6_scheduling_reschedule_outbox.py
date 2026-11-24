from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    CalendarSyncOutbox,
    Candidate,
    CandidateInvitation,
    HRDecision,
    Interview,
    InterviewAvailability,
    InterviewSlotReservation,
    Job,
    JobApplication,
    Organization,
    Resume,
    TransactionalEmailOutbox,
    User,
)
from app.services.scheduling_workflow_service import SchedulingWorkflowService
from app.services.calendar_outbox_service import CalendarOutboxService


def _seed_advanced_app(db):
    org = Organization(id=uuid.uuid4(), name="Org", status="active")
    interviewer = User(
        id=uuid.uuid4(),
        organization_id=org.id,
        email="hr@org.test",
        full_name="HR User",
        password_hash="x",
        role="recruiter",
        roles=["recruiter"],
        is_active=True,
        status="active",
    )
    candidate = Candidate(
        id=uuid.uuid4(),
        organization_id=org.id,
        full_name="Cand One",
        email="cand@example.com",
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
    db.add(
        HRDecision(
            id=uuid.uuid4(),
            job_application_id=app.id,
            user_id=interviewer.id,
            decision="advance",
        )
    )
    avail = InterviewAvailability(
        id=uuid.uuid4(),
        organization_id=org.id,
        interviewer_user_id=interviewer.id,
        scheduled_date=date.today() + timedelta(days=3),
        start_time="09:00",
        end_time="11:00",
        duration_minutes=60,
        timezone="UTC",
        status="available",
    )
    db.add(avail)
    db.flush()
    return org, interviewer, candidate, job, app, avail


def test_invitation_creation_enqueues_outbox(db_session):
    org, interviewer, _cand, _job, app, _avail = _seed_advanced_app(db_session)
    issue = SchedulingWorkflowService().create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=app.id,
        actor_user_id=interviewer.id,
        expires_in_days=7,
    )
    db_session.flush()
    rows = list(db_session.scalars(select(TransactionalEmailOutbox)))
    assert issue.token
    assert any(r.template == "candidate_interview_invitation" for r in rows)


def test_book_then_reschedule_same_token_and_interview(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_calendar_mode", "hera")
    org, interviewer, _candidate, _job, app, avail = _seed_advanced_app(db_session)
    issue = SchedulingWorkflowService().create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=app.id,
        actor_user_id=interviewer.id,
        expires_in_days=7,
    )
    interview = SchedulingWorkflowService().candidate_book_slot(
        db_session,
        token=issue.token,
        availability_id=avail.id,
        scheduled_time="09:00",
    )
    db_session.flush()
    interview2 = SchedulingWorkflowService().candidate_book_slot(
        db_session,
        token=issue.token,
        availability_id=avail.id,
        scheduled_time="10:00",
    )
    db_session.flush()
    assert interview.id == interview2.id
    assert interview2.scheduled_time == "10:00"
    assert interview2.scheduled_start_at < interview2.scheduled_end_at
    inv = db_session.scalar(select(CandidateInvitation).where(CandidateInvitation.id == issue.invitation.id))
    assert inv is not None and inv.status == "booked"
    assert inv.reschedule_count >= 1
    outbox = list(db_session.scalars(select(TransactionalEmailOutbox)))
    assert any(r.template == "candidate_interview_rescheduled" for r in outbox)
    cal_outbox = list(db_session.scalars(select(CalendarSyncOutbox)))
    assert cal_outbox  # durable calendar outbox enqueued
    active_res = list(
        db_session.scalars(
            select(InterviewSlotReservation).where(
                InterviewSlotReservation.interview_id == interview2.id,
                InterviewSlotReservation.status == "active",
            )
        )
    )
    assert len(active_res) == 1
    assert interview2.calendar_sync_status == "pending"


def test_failed_reschedule_rolls_back_old_booking_and_event(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_calendar_mode", "hera")
    org, interviewer, _candidate, _job, app, avail = _seed_advanced_app(db_session)
    issue = SchedulingWorkflowService().create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=app.id,
        actor_user_id=interviewer.id,
        expires_in_days=7,
    )
    service = SchedulingWorkflowService()
    interview = service.candidate_book_slot(
        db_session, token=issue.token, availability_id=avail.id, scheduled_time="09:00"
    )
    db_session.flush()
    interview.google_event_id = "evt-old"
    db_session.flush()
    old_start = interview.scheduled_start_at
    old_end = interview.scheduled_end_at
    old_outbox_ids = {
        row.id
        for row in db_session.scalars(
            select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id)
        )
    }

    def fail_on_reschedule(self, db, **kwargs):
        raise RuntimeError("calendar outbox unavailable")

    monkeypatch.setattr(CalendarOutboxService, "enqueue", fail_on_reschedule)
    with pytest.raises(RuntimeError, match="calendar outbox unavailable"):
        with db_session.begin_nested():
            service.candidate_reschedule(
                db_session,
                token=issue.token,
                interview_id=interview.id,
                availability_id=avail.id,
                scheduled_time="10:00",
            )
    db_session.expire_all()

    restored = db_session.get(Interview, interview.id)
    assert restored.scheduled_start_at == old_start
    assert restored.scheduled_end_at == old_end
    assert restored.google_event_id == "evt-old"
    active_reservations = db_session.scalars(
        select(InterviewSlotReservation).where(
            InterviewSlotReservation.interview_id == interview.id,
            InterviewSlotReservation.status == "active",
        )
    ).all()
    assert len(active_reservations) == 1
    outbox_ids = {
        row.id
        for row in db_session.scalars(
            select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id)
        )
    }
    assert outbox_ids == old_outbox_ids
    assert db_session.scalars(
        select(TransactionalEmailOutbox).where(
            TransactionalEmailOutbox.template == "candidate_interview_rescheduled"
        )
    ).first() is None
