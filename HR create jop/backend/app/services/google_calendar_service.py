from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import HRGoogleConnection, Interview
from app.services.errors import ValidationError
from app.services.google_oauth_service import GoogleOAuthService
from app.services.interview_service import _to_minutes

logger = logging.getLogger(__name__)
GOOGLE_CAL_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarService:
    """Google FreeBusy checks and Calendar event create/update with HERA-only dev fallback."""

    def _mode(self) -> str:
        return (settings.google_calendar_mode or "hera").strip().lower()

    def is_google_mode(self) -> bool:
        return self._mode() == "google"

    def _hera_warn(self, action: str) -> None:
        if self._mode() == "hera" and settings.app_env != "production":
            logger.warning("HERA-only calendar mode active (%s): no real Google Calendar call made.", action)

    def ensure_hr_ready(self, db: Session, *, organization_id: uuid.UUID, interviewer_user_id: uuid.UUID | None) -> HRGoogleConnection | None:
        if interviewer_user_id is None:
            if self.is_google_mode():
                raise ValidationError("An interviewer with a valid Google Calendar connection is required.")
            self._hera_warn("no-interviewer")
            return None
        conn = GoogleOAuthService().get_connection(db, organization_id=organization_id, user_id=interviewer_user_id)
        if self.is_google_mode():
            if conn is None or conn.status != "connected":
                raise ValidationError("A valid Google Calendar connection is required for the interviewer.")
            return conn
        if conn is None or conn.status != "connected":
            self._hera_warn("missing-connection")
            return None
        return conn

    def check_freebusy(
        self,
        db: Session,
        conn: HRGoogleConnection | None,
        *,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
    ) -> bool:
        """Return True if slot is free (or in HERA-only mode without connection)."""
        if not self.is_google_mode():
            self._hera_warn("freebusy")
            return True
        if conn is None:
            raise ValidationError("A valid Google Calendar connection is required.")
        try:
            token = GoogleOAuthService().get_valid_access_token(db, conn)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("Could not verify Google Calendar availability. Try again.") from exc
        requested_calendar_id = calendar_id or conn.calendar_id or "primary"
        body = {
            "timeMin": start.astimezone(timezone.utc).isoformat(),
            "timeMax": end.astimezone(timezone.utc).isoformat(),
            "items": [{"id": requested_calendar_id}],
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{GOOGLE_CAL_BASE}/freeBusy",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
        if resp.status_code >= 400:
            # treat as not free/sync issue to be safe in google mode
            if self.is_google_mode():
                raise ValidationError("Could not verify Google Calendar availability. Try again.")
            return True
        data = resp.json() or {}
        calendars = data.get("calendars", {}) if isinstance(data, dict) else {}
        cal = calendars.get(requested_calendar_id) if isinstance(calendars, dict) else None
        if not isinstance(cal, dict) or cal.get("errors"):
            raise ValidationError("Could not verify Google Calendar availability. Try again.")
        busy = cal.get("busy")
        if not isinstance(busy, list):
            raise ValidationError("Could not verify Google Calendar availability. Try again.")
        return len(busy) == 0

    def _event_body(self, interview: Interview, *, timezone_name: str) -> dict[str, Any]:
        start_min = _to_minutes(interview.scheduled_time)
        start_dt = datetime.combine(
            interview.scheduled_date,
            datetime.min.time(),
            tzinfo=ZoneInfo(timezone_name),
        ) + timedelta(minutes=start_min)
        end_dt = start_dt + timedelta(minutes=interview.scheduled_duration_minutes or 60)
        candidate = interview.job_application.candidate
        job = interview.job_application.job
        summary = f"Interview: {candidate.full_name} - {job.title}"
        desc = f"HERA interview ({interview.interview_type})."
        return {
            "summary": summary,
            "description": desc,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_name},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_name},
        }

    def create_or_update_event(
        self,
        db: Session,
        interview: Interview,
        conn: HRGoogleConnection | None,
        *,
        timezone_name: str = "UTC",
    ) -> tuple[str | None, str | None, str, str | None]:
        """Returns (calendar_id, event_id, sync_status, error). Never raises secrets."""
        if conn is None or getattr(conn, "status", None) != "connected":
            if self.is_google_mode():
                return None, interview.google_event_id, "disconnected", "google_account_disconnected"
            self._hera_warn("create_or_update_event")
            return None, interview.google_event_id, "hera_only", None
        try:
            token = GoogleOAuthService().get_valid_access_token(db, conn)
        except ValidationError:
            if self.is_google_mode():
                # Token/credential issues (e.g. revoked/invalid/reconnect required) are account/auth problems.
                return (
                    conn.calendar_id or "primary",
                    interview.google_event_id,
                    "disconnected",
                    "google_account_disconnected",
                )
            return conn.calendar_id or "primary", interview.google_event_id, "hera_only", None
        except Exception:
            if self.is_google_mode():
                return conn.calendar_id or "primary", interview.google_event_id, "retryable_error", "google_api_temporary_failure"
            return conn.calendar_id or "primary", interview.google_event_id, "hera_only", None
        calendar_id = conn.calendar_id or "primary"
        body = self._event_body(interview, timezone_name=timezone_name)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(timeout=20.0) as client:
                if interview.google_event_id:
                    resp = client.patch(
                        f"{GOOGLE_CAL_BASE}/calendars/{calendar_id}/events/{interview.google_event_id}",
                        headers=headers,
                        json=body,
                    )
                    # if event was deleted externally, fall back to create for reconciliation
                    if resp.status_code == 404:
                        resp = client.post(
                            f"{GOOGLE_CAL_BASE}/calendars/{calendar_id}/events",
                            headers=headers,
                            json=body,
                        )
                else:
                    resp = client.post(
                        f"{GOOGLE_CAL_BASE}/calendars/{calendar_id}/events",
                        headers=headers,
                        json=body,
                    )
            if resp.status_code >= 400:
                if self.is_google_mode():
                    if resp.status_code in (401, 403):
                        return calendar_id, interview.google_event_id, "disconnected", "google_account_disconnected"
                    return calendar_id, interview.google_event_id, "retryable_error", "google_api_temporary_failure"
                return calendar_id, interview.google_event_id, "hera_only", None
            data = resp.json() or {}
            event_id = data.get("id") or interview.google_event_id
            return calendar_id, event_id, "synced", None
        except Exception:
            if self.is_google_mode():
                return calendar_id, interview.google_event_id, "retryable_error", "google_api_temporary_failure"
            return calendar_id, interview.google_event_id, "hera_only", None

    def delete_event(
        self,
        db: Session,
        conn: HRGoogleConnection | None,
        *,
        calendar_id: str,
        event_id: str,
    ) -> tuple[bool, str | None]:
        if not event_id:
            return True, None
        if conn is None or getattr(conn, "status", None) != "connected":
            if self.is_google_mode():
                return False, "google_account_disconnected"
            self._hera_warn("delete_event")
            return True, None
        try:
            token = GoogleOAuthService().get_valid_access_token(db, conn)
        except Exception:
            if self.is_google_mode():
                return False, "google_account_disconnected"
            return True, None
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.delete(
                    f"{GOOGLE_CAL_BASE}/calendars/{calendar_id or conn.calendar_id or 'primary'}/events/{event_id}",
                    headers=headers,
                )
            if resp.status_code in (200, 204, 404, 410):
                return True, None
            if self.is_google_mode():
                if resp.status_code in (401, 403):
                    return False, "google_account_disconnected"
                return False, "google_api_temporary_failure"
            return True, None
        except Exception:
            if self.is_google_mode():
                return False, "google_api_temporary_failure"
            return True, None
