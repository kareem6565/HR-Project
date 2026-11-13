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
    HRDecision,
    HRGoogleConnection,
    Interview,
    InterviewAvailability,
    InterviewSlotReservation,
    Job,
    JobApplication,
    Organization,
    Resume,
    User,
)
from app.services.calendar_outbox_service import CalendarOutboxService
from app.services.errors import ConflictError, ValidationError
from app.services.google_calendar_service import GoogleCalendarService
from app.services.interview_service import InterviewService
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


def _seed_hr_scheduling(db, *, calendar_id="primary"):
    org = Organization(id=uuid.uuid4(), name="Cal Org", status="active")
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
        full_name="Candidate Cal",
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
    conn = HRGoogleConnection(
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
    db.add(conn)
    day = date.today() + timedelta(days=5)
    avail = InterviewAvailability(
        id=uuid.uuid4(),
        organization_id=org.id,
        interviewer_user_id=interviewer.id,
        scheduled_date=day,
        start_time="11:00",
        end_time="13:00",
        duration_minutes=30,
        timezone="UTC",
        status="available",
    )
    db.add(avail)
    db.flush()
    return org, interviewer, candidate, job, app, avail, conn


class TestGoogleCalendarSyncOutbox:
    def test_freebusy_busy_and_calendar_errors_are_not_treated_as_free(
        self, db_session, google_mode_settings, monkeypatch
    ):
        org, interviewer, _candidate, _job, _app, _avail, conn = _seed_hr_scheduling(db_session)
        service = GoogleCalendarService()

        def responder(method, url, headers, body):
            if body["items"][0]["id"] == "primary":
                return FakeResponse(
                    200,
                    {"calendars": {"primary": {"busy": [{"start": "x", "end": "y"}]}}},
                )
            return FakeResponse(200, {"calendars": {"primary": {"errors": [{"reason": "forbidden"}]}}})

        with mock_google_http(monkeypatch, responder):
            assert not service.check_freebusy(
                db_session,
                conn,
                start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc) + timedelta(minutes=30),
                calendar_id="primary",
            )
            with pytest.raises(ValidationError, match="Could not verify"):
                service.check_freebusy(
                    db_session,
                    conn,
                    start=datetime.now(timezone.utc),
                    end=datetime.now(timezone.utc) + timedelta(minutes=30),
                    calendar_id="missing-calendar",
                )

    def test_hr_schedule_creates_outbox_atomically_and_syncs_event(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, candidate, job, _app, avail, conn = _seed_hr_scheduling(db_session, calendar_id="primary")
        event_id = "evt-created-123"

        def responder(method, url, headers, body):
            assert headers.get("Authorization") == "Bearer access-token"
            if method == "POST" and url.endswith("/freeBusy"):
                return FakeResponse(200, {"calendars": {"primary": {"busy": []}}})
            if method == "POST" and url.endswith("/calendars/primary/events"):
                assert body["start"]["timeZone"] == "UTC"
                assert body["end"]["timeZone"] == "UTC"
                assert "Candidate Cal" in body["summary"]
                assert "Backend Engineer" in body["summary"]
                assert "technical" in body.get("description", "").lower()
                # 12:00 UTC for 30 min
                assert body["start"]["dateTime"].startswith(f"{avail.scheduled_date.isoformat()}T12:00:00")
                assert body["end"]["dateTime"].startswith(f"{avail.scheduled_date.isoformat()}T12:30:00")
                return FakeResponse(200, {"id": event_id})
            raise AssertionError(f"unexpected call {method} {url}")

        with mock_google_http(monkeypatch, responder) as calls:
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
            outbox = db_session.scalars(
                select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id)
            ).all()
            assert len(outbox) == 1
            assert outbox[0].operation == "upsert_interview"
            assert outbox[0].status == "pending"

            processed = CalendarOutboxService().process_pending(db_session, limit=10)
            db_session.flush()
            assert processed == 1

        db_session.expire_all()
        interview = db_session.get(Interview, interview.id)
        assert interview is not None
        assert interview.google_event_id == event_id
        assert interview.google_calendar_id == "primary"
        assert interview.calendar_sync_status == "synced"
        assert interview.calendar_sync_error is None
        row = db_session.scalar(select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id))
        assert row is not None and row.status == "succeeded"
        assert [call[0] for call in calls] == ["POST", "POST"]

    def test_api_failure_retries_safely_without_duplicate_events(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, candidate, job, _app, avail, _conn = _seed_hr_scheduling(db_session)
        state = {"n": 0}
        event_id = "evt-retry-1"

        def responder(method, url, headers, body):
            if method == "POST" and url.endswith("/freeBusy"):
                return FakeResponse(200, {"calendars": {"primary": {"busy": []}}})
            if method == "POST" and "/events" in url:
                state["n"] += 1
                if state["n"] == 1:
                    return FakeResponse(503, {"error": "temporary"})
                return FakeResponse(200, {"id": event_id})
            raise AssertionError(f"unexpected call {method} {url}")

        with mock_google_http(monkeypatch, responder) as calls:
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

            assert CalendarOutboxService().process_one(db_session) is True
            db_session.flush()
            row = db_session.scalar(select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id))
            assert row is not None
            assert row.status == "pending"  # retry scheduled
            assert row.attempts == 1
            assert row.last_error == "google_api_temporary_failure"
            db_session.expire_all()
            interview = db_session.get(Interview, interview.id)
            assert interview.calendar_sync_status == "retryable_error"
            assert interview.calendar_sync_error == "google_api_temporary_failure"
            assert interview.google_event_id is None

            # make due and retry successfully
            row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db_session.flush()
            assert CalendarOutboxService().process_one(db_session) is True
            db_session.flush()

        db_session.expire_all()
        interview = db_session.get(Interview, interview.id)
        assert interview.google_event_id == event_id
        assert interview.calendar_sync_status == "synced"
        row = db_session.scalar(select(CalendarSyncOutbox).where(CalendarSyncOutbox.interview_id == interview.id))
        assert row.status == "succeeded"
        # One failed create attempt + one successful create attempt; no duplicate event IDs created.
        assert [c[0] for c in calls if "/events" in c[1]] == ["POST", "POST"]

    def test_reschedule_updates_existing_event_using_stored_event_id(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, _candidate, _job, app, avail, conn = _seed_hr_scheduling(db_session)
        event_id = "evt-existing-999"

        def responder(method, url, headers, body):
            if method == "POST" and url.endswith("/calendars/primary/events"):
                return FakeResponse(200, {"id": event_id})
            if method == "PATCH" and url.endswith(f"/calendars/primary/events/{event_id}"):
                assert body["start"]["timeZone"] == "UTC"
                assert body["start"]["dateTime"].startswith(f"{avail.scheduled_date.isoformat()}T12:30:00")
                assert body["end"]["dateTime"].startswith(f"{avail.scheduled_date.isoformat()}T13:00:00")
                return FakeResponse(200, {"id": event_id})
            if method == "POST" and url.endswith("/freeBusy"):
                return FakeResponse(200, {"calendars": {"primary": {"busy": []}}})
            raise AssertionError(f"unexpected call {method} {url}")

        # avoid external freebusy variability in candidate booking path; focus on sync behavior
        monkeypatch.setattr(GoogleCalendarService, "check_freebusy", lambda *a, **k: True)

        with mock_google_http(monkeypatch, responder) as calls:
            issue = SchedulingWorkflowService().create_invitation(
                db_session,
                organization_id=org.id,
                job_application_id=app.id,
                actor_user_id=interviewer.id,
                expires_in_days=7,
            )
            interview = SchedulingWorkflowService().candidate_book_slot(
                db_session, token=issue.token, availability_id=avail.id, scheduled_time="12:00"
            )
            db_session.flush()
            CalendarOutboxService().process_pending(db_session, limit=10)
            db_session.flush()

            interview2 = SchedulingWorkflowService().candidate_book_slot(
                db_session, token=issue.token, availability_id=avail.id, scheduled_time="12:30"
            )
            db_session.flush()
            assert interview.id == interview2.id
            CalendarOutboxService().process_pending(db_session, limit=10)
            db_session.flush()

        db_session.expire_all()
        interview = db_session.get(Interview, interview.id)
        assert interview.google_event_id == event_id
        assert interview.calendar_sync_status == "synced"
        # initial create then update (PATCH) on same stored event id, not a new create
        sync_calls = [c for c in calls if "/events" in c[1]]
        assert [c[0] for c in sync_calls] == ["POST", "PATCH"]

    def test_uses_correct_hr_users_primary_calendar(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, candidate, job, _app, avail, _conn = _seed_hr_scheduling(db_session, calendar_id="primary")
        seen_urls = []

        def responder(method, url, headers, body):
            seen_urls.append(url)
            if method == "POST" and url.endswith("/freeBusy"):
                return FakeResponse(200, {"calendars": {"primary": {"busy": []}}})
            if method == "POST":
                return FakeResponse(200, {"id": "evt-primary"})
            raise AssertionError(f"unexpected call {method} {url}")

        with mock_google_http(monkeypatch, responder):
            interview = InterviewService().schedule(
                db_session,
                organization_id=org.id,
                candidate_id=candidate.id,
                job_id=job.id,
                interview_type="technical",
                scheduled_date=avail.scheduled_date,
                scheduled_time="11:30",
                interviewer_user_id=interviewer.id,
                scheduled_duration_minutes=30,
            )
            db_session.flush()
            CalendarOutboxService().process_pending(db_session, limit=10)
            db_session.flush()

        assert any(url.endswith("/calendars/primary/events") for url in seen_urls)

    def test_disconnected_account_distinguished_from_temporary_failure(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, candidate, job, app, avail, conn = _seed_hr_scheduling(db_session)
        conn.status = "disconnected"
        db_session.flush()

        with pytest.raises(ValidationError, match="valid Google Calendar connection"):
            InterviewService().schedule(
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
        assert db_session.scalar(select(Interview).where(Interview.job_application_id == app.id)) is None
        assert db_session.scalar(select(CalendarSyncOutbox).where(CalendarSyncOutbox.organization_id == org.id)) is None

    def test_hr_busy_slot_rejects_before_creating_rows(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, candidate, job, app, avail, _conn = _seed_hr_scheduling(db_session)
        monkeypatch.setattr(GoogleCalendarService, "check_freebusy", lambda *a, **k: False)
        with pytest.raises(ConflictError, match="Google Calendar"):
            InterviewService().schedule(
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
        assert db_session.scalar(select(Interview).where(Interview.job_application_id == app.id)) is None
        assert db_session.scalar(select(CalendarSyncOutbox).where(CalendarSyncOutbox.organization_id == org.id)) is None

    def test_hr_freebusy_outage_rejects_before_creating_rows(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, candidate, job, app, avail, _conn = _seed_hr_scheduling(db_session)
        monkeypatch.setattr(
            GoogleCalendarService,
            "check_freebusy",
            lambda *a, **k: (_ for _ in ()).throw(
                ValidationError("Could not verify Google Calendar availability. Try again.")
            ),
        )
        with pytest.raises(ValidationError, match="Could not verify"):
            InterviewService().schedule(
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
        assert db_session.scalar(select(Interview).where(Interview.job_application_id == app.id)) is None
        assert db_session.scalar(select(CalendarSyncOutbox).where(CalendarSyncOutbox.organization_id == org.id)) is None

    def test_cancellation_syncs_safely(self, db_session, google_mode_settings, monkeypatch):
        org, interviewer, candidate, job, _app, avail, _conn = _seed_hr_scheduling(db_session)
        event_id = "evt-cancel-1"

        def responder(method, url, headers, body):
            if method == "POST" and url.endswith("/freeBusy"):
                return FakeResponse(200, {"calendars": {"primary": {"busy": []}}})
            if method == "POST" and url.endswith("/calendars/primary/events"):
                return FakeResponse(200, {"id": event_id})
            if method == "DELETE" and url.endswith(f"/calendars/primary/events/{event_id}"):
                return FakeResponse(204, {})
            raise AssertionError(f"unexpected call {method} {url}")

        with mock_google_http(monkeypatch, responder) as calls:
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
            CalendarOutboxService().process_pending(db_session, limit=10)
            db_session.flush()
            InterviewService().cancel(db_session, interview_id=interview.id, organization_id=org.id)
            db_session.flush()
            CalendarOutboxService().process_pending(db_session, limit=10)
            db_session.flush()

        db_session.expire_all()
        interview = db_session.get(Interview, interview.id)
        assert interview is not None
        assert interview.status == "cancelled"
        assert interview.calendar_sync_status == "cancelled"
        assert interview.calendar_sync_error is None
        cancel_rows = db_session.scalars(
            select(CalendarSyncOutbox).where(
                CalendarSyncOutbox.interview_id == interview.id,
                CalendarSyncOutbox.operation == "cancel_event",
            )
        ).all()
        assert any(r.status == "succeeded" for r in cancel_rows)
        assert any(c[0] == "DELETE" for c in calls)

    def test_disconnected_outbox_requires_explicit_requeue(self, db_session):
        org = Organization(id=uuid.uuid4(), name="Outbox Org", status="active")
        db_session.add(org)
        db_session.flush()
        row = CalendarSyncOutbox(
            id=uuid.uuid4(),
            organization_id=org.id,
            operation="upsert_interview",
            idempotency_key=f"disconnected-{uuid.uuid4()}",
            payload={},
            status="failed",
            attempts=1,
            max_attempts=8,
            next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            last_error="google_account_disconnected",
        )
        db_session.add(row)
        db_session.flush()
        assert CalendarOutboxService().claim_next(db_session) is None
        assert CalendarOutboxService().requeue_disconnected(db_session) == 1
        claimed = CalendarOutboxService().claim_next(db_session)
        assert claimed is not None
        assert claimed.status == "processing"

    def test_cancellation_enqueue_failure_rolls_back_hera_change(
        self, db_session, google_mode_settings, monkeypatch
    ):
        org, interviewer, candidate, job, _app, avail, _conn = _seed_hr_scheduling(db_session)
        monkeypatch.setattr(GoogleCalendarService, "check_freebusy", lambda *a, **k: True)
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
        interview.google_event_id = "evt-existing"
        db_session.flush()
        original_status = interview.status

        def fail_enqueue(*args, **kwargs):
            raise RuntimeError("outbox unavailable")

        monkeypatch.setattr(CalendarOutboxService, "enqueue", fail_enqueue)
        with pytest.raises(RuntimeError, match="outbox unavailable"):
            with db_session.begin_nested():
                InterviewService().cancel(
                    db_session, interview_id=interview.id, organization_id=org.id
                )
        db_session.expire_all()
        restored = db_session.get(Interview, interview.id)
        assert restored.status == original_status
        assert restored.google_event_id == "evt-existing"
        reservation = db_session.scalar(
            select(InterviewSlotReservation).where(
                InterviewSlotReservation.interview_id == interview.id,
                InterviewSlotReservation.status == "active",
            )
        )
        assert reservation is not None
        assert db_session.scalar(
            select(CalendarSyncOutbox).where(
                CalendarSyncOutbox.interview_id == interview.id,
                CalendarSyncOutbox.operation == "cancel_event",
            )
        ) is None
