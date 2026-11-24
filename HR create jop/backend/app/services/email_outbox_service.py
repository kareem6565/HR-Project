from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TransactionalEmailOutbox
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class EmailOutboxService:
    """Durable transactional outbox with Console Provider and async worker processing."""

    def enqueue(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID | None,
        recipient: str,
        subject: str,
        template: str,
        payload: dict[str, Any],
    ) -> TransactionalEmailOutbox:
        # Never store raw tokens/booking URLs/email bodies beyond safe payload fields; caller must sanitize.
        now = datetime.now(UTC)
        row = TransactionalEmailOutbox(
            organization_id=organization_id,
            recipient=recipient,
            subject=subject,
            template=template,
            payload=payload or {},
            status="pending",
            attempts=0,
            max_attempts=5,
            next_attempt_at=now,
            provider="console",
        )
        db.add(row)
        db.flush()
        AuditService().log_event(
            db,
            action="email_outbox.enqueued",
            entity_type="transactional_email_outbox",
            organization_id=organization_id,
            actor_user_id=None,
            entity_id=row.id,
            metadata={"template": template, "status": row.status},
            flush=False,
        )
        return row

    def claim_next(self, db: Session, *, now: datetime | None = None) -> TransactionalEmailOutbox | None:
        now = now or datetime.now(UTC)
        stmt = (
            select(TransactionalEmailOutbox)
            .where(
                TransactionalEmailOutbox.status.in_(["pending", "failed"]),
                TransactionalEmailOutbox.next_attempt_at <= now,
                TransactionalEmailOutbox.attempts < TransactionalEmailOutbox.max_attempts,
            )
            .order_by(TransactionalEmailOutbox.next_attempt_at.asc(), TransactionalEmailOutbox.created_at.asc())
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

    def deliver_console(self, row: TransactionalEmailOutbox) -> None:
        recipient_hash = hashlib.sha256(row.recipient.encode("utf-8")).hexdigest()[:12]
        logger.info(
            "OUTBOX_EMAIL provider=console template=%s recipient_hash=%s id=%s",
            row.template,
            recipient_hash,
            row.id,
        )

    def mark_sent(self, row: TransactionalEmailOutbox, *, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        row.status = "sent"
        row.sent_at = now
        row.last_error = None
        row.updated_at = now

    def mark_failure(self, row: TransactionalEmailOutbox, error: str, *, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        row.last_error = (error or "delivery_failed")[:500]
        row.updated_at = now
        if row.attempts >= (row.max_attempts or 5):
            row.status = "failed"
            row.next_attempt_at = now
        else:
            row.status = "pending"
            delay = min(300, 5 * (2 ** max(0, row.attempts - 1)))
            row.next_attempt_at = now + timedelta(seconds=delay)

    def process_one(self, db: Session) -> bool:
        row = self.claim_next(db)
        if row is None:
            return False
        try:
            self.deliver_console(row)
            self.mark_sent(row)
        except Exception:
            self.mark_failure(row, "console_delivery_failed")
        db.flush()
        return True

    def process_pending(self, db: Session, *, limit: int = 20) -> int:
        count = 0
        for _ in range(limit):
            if not self.process_one(db):
                break
            count += 1
        return count
