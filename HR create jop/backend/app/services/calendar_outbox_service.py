from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarSyncOutbox, HRGoogleConnection, Interview
from app.services.audit_service import AuditService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.google_oauth_service import GoogleOAuthService

logger = logging.getLogger(__name__)


class CalendarOutboxService:
    """Durable calendar sync outbox with retries, idempotency, and reconciliation."""

    def enqueue(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        interview_id: uuid.UUID | None,
        hr_user_id: uuid.UUID | None,
        operation: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> CalendarSyncOutbox:
        existing = db.scalar(
            select(CalendarSyncOutbox).where(CalendarSyncOutbox.idempotency_key == idempotency_key)
        )
        if existing is not None:
            # Reconcile/retry: if failed or pending, keep it; if succeeded, idempotent no-op.
            if existing.status in {"failed", "succeeded"}:
                # For reconciliation, allow requeue when caller explicitly wants same key reused? keep idempotent.
                pass
            return existing
        now = datetime.now(UTC)
        row = CalendarSyncOutbox(
            organization_id=organization_id,
            interview_id=interview_id,
            hr_user_id=hr_user_id,
            operation=operation,
            idempotency_key=idempotency_key,
            payload=payload or {},
            status="pending",
            attempts=0,
            max_attempts=8,
            next_attempt_at=now,
        )
        db.add(row)
        db.flush()
        AuditService().log_event(
            db,
            action="calendar_outbox.enqueued",
            entity_type="calendar_sync_outbox",
            organization_id=organization_id,
            actor_user_id=None,
            entity_id=row.id,
            metadata={"operation": operation, "status": row.status},
            flush=False,
        )
        return row

    def claim_next(self, db: Session, *, now: datetime | None = None) -> CalendarSyncOutbox | None:
        now = now or datetime.now(UTC)
        stmt = (
            select(CalendarSyncOutbox)
            .where(
                CalendarSyncOutbox.status == "pending",
                CalendarSyncOutbox.next_attempt_at <= now,
                CalendarSyncOutbox.attempts < CalendarSyncOutbox.max_attempts,
            )
            .order_by(CalendarSyncOutbox.next_attempt_at.asc(), CalendarSyncOutbox.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        row = db.execute(stmt).scalars().first()
        if row is None:
            return None
        row.status = "processing"
        row.attempts += 1
        row.updated_at = now
        db.flush()
        return row

    def requeue_disconnected(
        self, db: Session, *, interview_id: uuid.UUID | None = None
    ) -> int:
        """Explicitly requeue user-action-required rows after reconnection."""
        statement = select(CalendarSyncOutbox).where(
            CalendarSyncOutbox.status == "failed",
            CalendarSyncOutbox.last_error == "google_account_disconnected",
        )
        if interview_id is not None:
            statement = statement.where(CalendarSyncOutbox.interview_id == interview_id)
        rows = list(db.scalars(statement.with_for_update()))
        now = datetime.now(UTC)
        for row in rows:
            row.status = "pending"
            row.next_attempt_at = now
            row.last_error = None
        db.flush()
        return len(rows)

    def mark_success(self, row: CalendarSyncOutbox, *, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        row.status = "succeeded"
        row.processed_at = now
        row.last_error = None
        row.updated_at = now

    def mark_failure(self, row: CalendarSyncOutbox, error: str, *, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        row.last_error = (error or "calendar_sync_failed")[:500]
        row.updated_at = now
        # Disconnected account requires user action; do not keep retrying as a transient API failure.
        if row.last_error == "google_account_disconnected":
            row.status = "failed"
            row.next_attempt_at = now
            return
        if row.attempts >= (row.max_attempts or 8):
            row.status = "failed"
            row.next_attempt_at = now
        else:
            row.status = "pending"
            delay = min(900, 10 * (2 ** max(0, row.attempts - 1)))
            row.next_attempt_at = now + timedelta(seconds=delay)

    def _apply_operation(self, db: Session, row: CalendarSyncOutbox) -> None:
        payload = row.payload or {}
        gcal = GoogleCalendarService()

        if row.operation == "upsert_interview":
            interview_id = payload.get("interview_id") or (str(row.interview_id) if row.interview_id else None)
            if not interview_id:
                raise ValueError("missing_interview_id")
            interview = db.get(Interview, uuid.UUID(interview_id))
            if interview is None:
                return
            if interview.status == "cancelled":
                # reconciled by cancellation op if needed
                interview.calendar_sync_status = "cancelled"
                interview.calendar_sync_error = None
                return
            hr_user_id = payload.get("hr_user_id") or (str(row.hr_user_id) if row.hr_user_id else None)
            conn = None
            if hr_user_id:
                conn = GoogleOAuthService().get_connection(
                    db, organization_id=interview.organization_id, user_id=uuid.UUID(hr_user_id)
                )
            elif interview.interviewer_user_id:
                conn = GoogleOAuthService().get_connection(
                    db, organization_id=interview.organization_id, user_id=interview.interviewer_user_id
                )
            timezone_name = payload.get("timezone") or "UTC"
            cal_id, event_id, status, err = gcal.create_or_update_event(
                db, interview, conn, timezone_name=timezone_name
            )
            interview.google_calendar_id = cal_id or interview.google_calendar_id
            interview.google_event_id = event_id or interview.google_event_id
            interview.calendar_sync_status = status
            interview.calendar_sync_error = err
            if gcal.is_google_mode() and status != "synced":
                raise ValueError(err or "google_sync_failed")
            return

        if row.operation == "cancel_event":
            hr_user_id = payload.get("hr_user_id") or (str(row.hr_user_id) if row.hr_user_id else None)
            calendar_id = payload.get("calendar_id")
            event_id = payload.get("event_id")
            if not event_id:
                return
            conn = None
            if hr_user_id:
                conn = GoogleOAuthService().get_connection(
                    db, organization_id=row.organization_id, user_id=uuid.UUID(hr_user_id)
                )
            ok, err = gcal.delete_event(db, conn, calendar_id=calendar_id or "primary", event_id=event_id)
            if gcal.is_google_mode() and not ok:
                if row.interview_id:
                    interview = db.get(Interview, row.interview_id)
                    if interview and interview.google_event_id == event_id:
                        interview.calendar_sync_error = err
                raise ValueError(err or "google_delete_failed")
            # mark related interview if present
            if row.interview_id:
                interview = db.get(Interview, row.interview_id)
                if interview and interview.google_event_id == event_id:
                    interview.calendar_sync_status = "cancelled"
                    interview.calendar_sync_error = None
            return

        # unknown ops are treated as no-op success for forward compatibility
        return

    def process_one(self, db: Session) -> bool:
        row = self.claim_next(db)
        if row is None:
            return False
        try:
            self._apply_operation(db, row)
            self.mark_success(row)
        except Exception as exc:
            # Preserve sanitized, classified sync errors (e.g. disconnected vs temporary failure)
            # without storing raw provider messages/tokens.
            err = str(exc) if isinstance(exc, ValueError) and str(exc) else type(exc).__name__
            self.mark_failure(row, err)
            logger.warning(
                "Calendar outbox operation failed operation=%s status=%s error=%s",
                row.operation,
                row.status,
                row.last_error,
            )
        db.flush()
        return True

    def process_pending(self, db: Session, *, limit: int = 20) -> int:
        count = 0
        for _ in range(limit):
            if not self.process_one(db):
                break
            count += 1
        return count
