from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.models import HRGoogleConnection, HRGoogleOAuthState, User
from app.services.audit_service import AuditService
from app.services.errors import NotFoundError, ValidationError

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
OAUTH_STATE_TTL = timedelta(minutes=10)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_state_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class GoogleOAuthService:
    """Per-HR Google OAuth with encrypted token storage."""

    def build_authorize_url(self, *, state: str) -> str:
        if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
            raise ValidationError("Google OAuth is not configured.")
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def create_state(
        self, db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> str:
        """Create a short-lived, one-time OAuth state bound to the initiating HR user.

        Returns the unhashed token for use in the authorize URL; only its SHA-256 hash is stored.
        """
        token = secrets.token_urlsafe(32)
        record = HRGoogleOAuthState(
            organization_id=organization_id,
            user_id=user_id,
            token_hash=_hash_state_token(token),
            expires_at=_utcnow() + OAUTH_STATE_TTL,
            used_at=None,
        )
        db.add(record)
        db.flush()
        return token

    def consume_state(self, db: Session, state: str) -> tuple[uuid.UUID, uuid.UUID]:
        """Atomically validate and consume a one-time OAuth state.

        Uses a row lock in a transaction so concurrent callbacks cannot replay the same state.
        Consumption is committed immediately and is never reusable, even if downstream processing fails.
        """
        if not state or not state.strip():
            raise ValidationError("Invalid Google OAuth state.")
        token_hash = _hash_state_token(state.strip())
        now = _utcnow()
        record = db.scalar(
            select(HRGoogleOAuthState)
            .where(HRGoogleOAuthState.token_hash == token_hash)
            .with_for_update()
        )
        if record is None:
            raise ValidationError("Invalid Google OAuth state.")
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if record.used_at is not None or expires_at <= now:
            raise ValidationError("Invalid or expired Google OAuth state.")
        record.used_at = now
        db.commit()
        return record.organization_id, record.user_id

    # Backward-compatible aliases for any existing callers; new code should use create_state/consume_state.
    def make_state(
        self, db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> str:
        return self.create_state(db, organization_id=organization_id, user_id=user_id)

    def parse_state(self, db: Session, state: str) -> tuple[uuid.UUID, uuid.UUID]:
        return self.consume_state(db, state)

    def exchange_code(self, code: str) -> dict[str, Any]:
        if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
            raise ValidationError("Google OAuth client credentials are not configured.")
        data = {
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
        if resp.status_code >= 400:
            raise ValidationError("Failed to exchange Google OAuth code.")
        return resp.json()

    def fetch_userinfo(self, access_token: str) -> dict[str, Any]:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code >= 400:
            return {}
        return resp.json()

    def upsert_connection(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        token_payload: dict[str, Any],
    ) -> HRGoogleConnection:
        user = db.get(User, user_id)
        if user is None or user.organization_id != organization_id:
            raise NotFoundError("User was not found.")
        access_token = token_payload.get("access_token")
        if not access_token:
            raise ValidationError("Google OAuth did not return an access token.")
        refresh_token = token_payload.get("refresh_token")
        expires_in = token_payload.get("expires_in")
        expiry = None
        if isinstance(expires_in, (int, float)):
            expiry = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        scope_str = token_payload.get("scope")
        info = self.fetch_userinfo(access_token)
        google_email = info.get("email") if isinstance(info, dict) else None

        conn = db.scalar(
            select(HRGoogleConnection).where(
                HRGoogleConnection.organization_id == organization_id,
                HRGoogleConnection.user_id == user_id,
            )
        )
        if conn is None:
            conn = HRGoogleConnection(
                organization_id=organization_id,
                user_id=user_id,
                calendar_id="primary",
                access_token_encrypted=encrypt_secret(access_token),
                refresh_token_encrypted=encrypt_secret(refresh_token) if refresh_token else None,
                token_expiry=expiry,
                scopes=scope_str,
                google_email=google_email,
                status="connected",
                last_error=None,
            )
            db.add(conn)
        else:
            conn.access_token_encrypted = encrypt_secret(access_token)
            if refresh_token:
                conn.refresh_token_encrypted = encrypt_secret(refresh_token)
            conn.token_expiry = expiry
            conn.scopes = scope_str or conn.scopes
            conn.google_email = google_email or conn.google_email
            conn.status = "connected"
            conn.last_error = None
        db.flush()
        AuditService().log_event(
            db,
            action="hr_google_connection.connected",
            entity_type="hr_google_connection",
            organization_id=organization_id,
            actor_user_id=user_id,
            entity_id=conn.id,
            metadata={"calendar_id": conn.calendar_id},
            flush=False,
        )
        return conn

    def get_connection(
        self, db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> HRGoogleConnection | None:
        return db.scalar(
            select(HRGoogleConnection).where(
                HRGoogleConnection.organization_id == organization_id,
                HRGoogleConnection.user_id == user_id,
            )
        )

    def require_connection(
        self, db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> HRGoogleConnection:
        conn = self.get_connection(db, organization_id=organization_id, user_id=user_id)
        if conn is None or conn.status != "connected":
            raise ValidationError("A valid Google Calendar connection is required.")
        return conn

    def disconnect(
        self, db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        conn = self.get_connection(db, organization_id=organization_id, user_id=user_id)
        if conn is None:
            return
        conn.status = "disconnected"
        conn.last_error = None
        db.flush()
        AuditService().log_event(
            db,
            action="hr_google_connection.disconnected",
            entity_type="hr_google_connection",
            organization_id=organization_id,
            actor_user_id=user_id,
            entity_id=conn.id,
            metadata={},
            flush=False,
        )

    def get_valid_access_token(self, db: Session, conn: HRGoogleConnection) -> str:
        now = datetime.now(timezone.utc)
        if conn.token_expiry and conn.token_expiry.tzinfo is None:
            expiry = conn.token_expiry.replace(tzinfo=timezone.utc)
        else:
            expiry = conn.token_expiry
        if expiry is None or expiry - now > timedelta(seconds=60):
            return decrypt_secret(conn.access_token_encrypted)
        # refresh
        if not conn.refresh_token_encrypted:
            conn.status = "error"
            conn.last_error = "Missing refresh token"
            db.flush()
            raise ValidationError("Google Calendar connection needs to be reconnected.")
        data = {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "refresh_token": decrypt_secret(conn.refresh_token_encrypted),
            "grant_type": "refresh_token",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
        if resp.status_code >= 400:
            conn.status = "error"
            conn.last_error = "Token refresh failed"
            db.flush()
            raise ValidationError("Google Calendar connection needs to be reconnected.")
        payload = resp.json()
        access_token = payload.get("access_token")
        if not access_token:
            conn.status = "error"
            conn.last_error = "Token refresh failed"
            db.flush()
            raise ValidationError("Google Calendar connection needs to be reconnected.")
        conn.access_token_encrypted = encrypt_secret(access_token)
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, (int, float)):
            conn.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        conn.status = "connected"
        conn.last_error = None
        db.flush()
        return access_token

    def status_payload(self, conn: HRGoogleConnection | None) -> dict[str, Any]:
        if conn is None:
            return {"connected": False, "status": "not_connected"}
        return {
            "connected": conn.status == "connected",
            "status": conn.status,
            "google_email": conn.google_email,
            "calendar_id": conn.calendar_id,
            "token_expiry": conn.token_expiry.isoformat() if conn.token_expiry else None,
            "last_error": conn.last_error,
        }
