from __future__ import annotations

from app.services.outbox_worker import OutboxWorker


class _FakeDb:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_worker_runs_email_and_calendar_claimers(monkeypatch):
    sessions = []

    def factory():
        session = _FakeDb()
        sessions.append(session)
        return session

    monkeypatch.setattr("app.services.outbox_worker.EmailOutboxService.process_one", lambda self, db: False)
    monkeypatch.setattr(
        "app.services.calendar_outbox_service.CalendarOutboxService.process_one",
        lambda self, db: True,
    )

    assert OutboxWorker(session_factory=factory).run_once() is True
    assert len(sessions) == 2
    assert sessions[0].rollbacks == 1
    assert sessions[1].commits == 1
