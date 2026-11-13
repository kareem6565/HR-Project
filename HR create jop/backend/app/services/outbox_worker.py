from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.core.database import SessionLocal
from app.services.email_outbox_service import EmailOutboxService

logger = logging.getLogger("app.outbox_worker")


class OutboxWorker:
    """Background worker for durable outboxes (email + calendar sync)."""

    def __init__(self, *, session_factory: Any | None = None) -> None:
        self.session_factory = session_factory or SessionLocal
        self.should_stop = False
        self.stop_event = threading.Event()

    def request_shutdown(self) -> None:
        self.should_stop = True
        self.stop_event.set()

    def run_once(self) -> bool:
        processed = False
        try:
            with self.session_factory() as db:
                try:
                    if EmailOutboxService().process_one(db):
                        processed = True
                        db.commit()
                    else:
                        db.rollback()
                except Exception:
                    db.rollback()
                    logger.exception("Email outbox processing iteration failed")
        except Exception:
            logger.exception("Email outbox session failed")

        # Calendar outbox processing is handled in calendar_outbox_service module if present.
        # Failures must be visible for diagnostics/retries; never swallow them silently.
        try:
            from app.services.calendar_outbox_service import CalendarOutboxService

            with self.session_factory() as db:
                try:
                    if CalendarOutboxService().process_one(db):
                        processed = True
                        db.commit()
                    else:
                        db.rollback()
                except Exception:
                    db.rollback()
                    logger.exception("Calendar outbox processing iteration failed")
        except Exception:
            logger.exception("Calendar outbox processing unavailable or failed before iteration")

        return processed

    def run_loop(self, poll_interval_seconds: float = 2.0) -> None:
        logger.info("Outbox worker started.")
        while not self.should_stop and not self.stop_event.is_set():
            try:
                if not self.run_once():
                    self.stop_event.wait(timeout=poll_interval_seconds)
            except Exception:
                logger.exception("Unhandled error in outbox worker loop")
                self.stop_event.wait(timeout=poll_interval_seconds)
        logger.info("Outbox worker stopped.")
