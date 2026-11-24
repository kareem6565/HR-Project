from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.crypto import encrypt_secret
from app.models import (
    CalendarSyncOutbox,
    Candidate,
    CandidateInvitation,
    HRDecision,
    HRGoogleConnection,
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
from app.services.calendar_outbox_service import CalendarOutboxService
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.scheduling_workflow_service import SchedulingWorkflowService


class FakeResponse:
    def __init__(self, status_code: int, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


class FakeHTTPClient:
    def __init__(self, responder, recorder, *args, **kwargs):
        self._responder = responder
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        self._recorder.append(("POST", url, headers or {}, json))
        return self._responder("POST", url, headers or {}, json)

    def patch(self, url, headers=None, json=None):
        self._recorder.append(("PATCH", url, headers or {}, json))
        return self._responder("PATCH", url, headers or {}, json)

    def delete(self, url, headers=None):
        self._recorder.append(("DELETE", url, headers or {}, None))
        return self._responder("DELETE", url, headers or {}, None)

    def get(self, url, headers=None):
        self._recorder.append(("GET", url, headers or {}, None))
        return self._responder("GET", url, headers or {}, None)


@contextmanager
def mock_google_http(monkeypatch, responder):
    calls = []

    def factory(*args, **kwargs):
        return FakeHTTPClient(responder, calls, *args, **kwargs)

    monkeypatch.setattr("app.services.google_calendar_service.httpx.Client", factory)
    yield calls


@pytest.fixture()
def google_mode_settings(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_calendar_mode", "google")
    monkeypatch.setattr(settings, "google_oauth_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "google_oauth_redirect_uri", "http://localhost:8000/api/v1/hr/google/callback")
    monkeypatch.setattr(settings, "google_token_encryption_key", "test-google-token-encryption-key-32chars")
    monkeypatch.setattr(settings, "app_env", "test")
    return settings


def _seed(db, *, with_google_connection=False, calendar_id="primary"):
    org = Organization(id=uuid.uuid4(), name="Booking Org", status="active")
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
    job = Job(id=uuid.uuid4(), organization_id=org.id, title="Backend Engineer")
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
        scheduled_date=date.today() + timedelta(days=5),
        start_time="11:00",
        end_time="13:00",
        duration_minutes=30,
        timezone="UTC",
        status="available",
    )
    db.add(avail)
    if with_google_connection:
        db.add(
            HRGoogleConnection(
                id=uuid.uuid4(),
                organization_id=org.id,
                user_id=interviewer.id,
                google_email="hr-google@example.com",
                calendar_id=calendar_id,
                access_token_encrypted=encrypt_secret("access-token"),
                refresh_token_encrypted=encrypt_secret("refresh-token"),
                token_expiry=datetime.now(timezone.utc) + timedelta(hours=2),
                status="connected",
            )
        )
    db.flush()
    return org, interviewer, candidate, job, app, avail


def test_candidate_booking_creates_interview_and_outbox_atomically(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_calendar_mode", "hera")
    org, interviewer, _candidate, _job, app, avail = _seed(db_session)
    issue = SchedulingWorkflowService().create_invitation(
        db_session, organization_id=org.id, job_application_id=app.id, actor_user_id=interviewer.id
    )
    interview = SchedulingWorkflowService().candidate_book_slot(
        db_session, token=issue.token, availability_id=avail.id, scheduled_time="11:00"
    )
    db_session.flush()

    db_session.expire_all()
    stored = db_session.get(Interview, interview.id)
    inv = db_session.scalar(select(CandidateInvitation).where(CandidateInvitation.id == issue.invitation.id))
    assert stored is not None and stored.status == "scheduled"
    assert stored.calendar_sync_status == "pending"
    assert inv is not None and inv.status == "booked" and inv.booked_interview_id == interview.id
    calendar_rows = list(
        db_session.scalars(
            select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id)
        )
    )
    assert len(calendar_rows) == 1
    assert calendar_rows[0].operation == "upsert_interview"
    assert db_session.scalar(
        select(InterviewSlotReservation).where(
            InterviewSlotReservation.interview_id == interview.id,
            InterviewSlotReservation.status == "active",
        )
    ) is not None
    assert any(
        r.template == "candidate_interview_booked"
        for r in db_session.scalars(select(TransactionalEmailOutbox)).all()
    )


def test_invalid_or_expired_invitation_token_rejected(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_calendar_mode", "hera")
    org, interviewer, _candidate, _job, app, avail = _seed(db_session)
    issue = SchedulingWorkflowService().create_invitation(
        db_session, organization_id=org.id, job_application_id=app.id, actor_user_id=interviewer.id
    )
    with pytest.raises(NotFoundError):
        SchedulingWorkflowService().candidate_book_slot(
            db_session, token="not-a-real-token-" + "x" * 40, availability_id=avail.id, scheduled_time="11:00"
        )

    inv = db_session.get(CandidateInvitation, issue.invitation.id)
    inv.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    inv.status = "pending"
    db_session.flush()
    with pytest.raises(ValidationError):
        SchedulingWorkflowService().candidate_book_slot(
            db_session, token=issue.token, availability_id=avail.id, scheduled_time="11:00"
        )


def test_slot_no_longer_available_and_boundary_enforced(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_calendar_mode", "hera")
    org, interviewer, _candidate, _job, app, avail = _seed(db_session)
    issue = SchedulingWorkflowService().create_invitation(
        db_session, organization_id=org.id, job_application_id=app.id, actor_user_id=interviewer.id
    )
    # misaligned / outside published window
    with pytest.raises(ValidationError):
        SchedulingWorkflowService().candidate_book_slot(
            db_session, token=issue.token, availability_id=avail.id, scheduled_time="11:15"
        )
    with pytest.raises(ValidationError):
        SchedulingWorkflowService().candidate_book_slot(
            db_session, token=issue.token, availability_id=avail.id, scheduled_time="12:45"
        )

    avail.status = "cancelled"
    db_session.flush()
    with pytest.raises(ValidationError):
        SchedulingWorkflowService().candidate_book_slot(
            db_session, token=issue.token, availability_id=avail.id, scheduled_time="11:00"
        )


def test_google_sync_failure_after_successful_booking_is_retried_without_losing_booking(
    db_session, google_mode_settings, monkeypatch
):
    org, interviewer, _candidate, _job, app, avail = _seed(db_session, with_google_connection=True)
    state = {"n": 0}
    monkeypatch.setattr(
        "app.services.google_calendar_service.GoogleCalendarService.check_freebusy",
        lambda *a, **k: True,
    )

    def responder(method, url, headers, body):
        if method == "POST" and url.endswith("/calendars/primary/events"):
            state["n"] += 1
            if state["n"] == 1:
                return FakeResponse(503, {"error": "temporary"})
            return FakeResponse(200, {"id": "evt-after-retry"})
        raise AssertionError(f"unexpected call {method} {url}")

    with mock_google_http(monkeypatch, responder):
        issue = SchedulingWorkflowService().create_invitation(
            db_session, organization_id=org.id, job_application_id=app.id, actor_user_id=interviewer.id
        )
        interview = SchedulingWorkflowService().candidate_book_slot(
            db_session, token=issue.token, availability_id=avail.id, scheduled_time="11:00"
        )
        db_session.flush()

        # Booking is committed/persisted in DB even if sync fails on first attempt.
        assert db_session.get(Interview, interview.id) is not None
        assert CalendarOutboxService().process_one(db_session) is True
        db_session.flush()
        row = db_session.scalar(select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id))
        assert row is not None and row.status == "pending"
        assert row.last_error == "google_api_temporary_failure"
        interview = db_session.get(Interview, interview.id)
        assert interview.status == "scheduled"

        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.flush()
        assert CalendarOutboxService().process_one(db_session) is True
        db_session.flush()

    db_session.expire_all()
    interview = db_session.get(Interview, interview.id)
    assert interview.status == "scheduled"
    assert interview.calendar_sync_status == "synced"
    assert interview.google_event_id == "evt-after-retry"
