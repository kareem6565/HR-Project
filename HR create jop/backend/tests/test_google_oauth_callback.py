from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.crypto import decrypt_secret
from app.core.database import get_db
from app.models import HRGoogleConnection, HRGoogleOAuthState, Organization, User
from app.services.google_oauth_service import GoogleOAuthService


@pytest.fixture()
def client(db_session):
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def seeded_org_user(db_session):
    org = Organization(name="OAuth Test Org", status="active")
    db_session.add(org)
    db_session.flush()
    user = User(
        organization_id=org.id,
        email="hr-oauth@example.com",
        full_name="HR OAuth",
        role="recruiter",
        status="active",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    org_id, user_id = org.id, user.id
    db_session.commit()
    return org_id, user_id


@pytest.fixture()
def oauth_settings(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_oauth_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "google_oauth_redirect_uri", "http://localhost:8000/api/v1/hr/google/callback")
    monkeypatch.setattr(settings, "google_oauth_post_login_redirect_uri", "http://localhost:5174/interviews/availability")
    monkeypatch.setattr(settings, "frontend_base_url", "http://localhost:5174")
    monkeypatch.setattr(settings, "google_calendar_mode", "google")
    monkeypatch.setattr(settings, "google_token_encryption_key", "test-google-token-encryption-key-32chars")
    return settings


def auth_headers(org_id, user_id) -> dict[str, str]:
    return {"X-User-Id": str(org_id and user_id and user_id), "X-Organization-Id": str(org_id)} if False else {"X-User-Id": str(user_id), "X-Organization-Id": str(org_id)}


class TestGoogleOAuthRoutesAuthBoundary:
    def test_connect_status_disconnect_require_auth_callback_is_public(self, client, db_session, seeded_org_user, oauth_settings):
        org_id, user_id = seeded_org_user

        # Protected routes reject unauthenticated requests
        assert client.get("/api/v1/hr/google/status").status_code == 401
        assert client.get("/api/v1/hr/google/connect").status_code == 401
        assert client.delete("/api/v1/hr/google/disconnect").status_code == 401

        # Protected routes work for authenticated HR user
        headers = auth_headers(org_id, user_id)
        status_resp = client.get("/api/v1/hr/google/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json().get("connected") is False

        connect_resp = client.get("/api/v1/hr/google/connect", headers=headers)
        assert connect_resp.status_code == 200
        assert "authorize_url" in connect_resp.json()

        # Callback is reachable without HERA auth (redirects with safe error when params/state invalid)
        cb_resp = client.get("/api/v1/hr/google/callback", follow_redirects=False)
        assert cb_resp.status_code in (302, 307)
        assert "google=error" in cb_resp.headers.get("location", "")


class TestGoogleOAuthCallback:
    def test_two_hera_users_connect_and_disconnect_independently(
        self, client, db_session, seeded_org_user, oauth_settings, monkeypatch
    ):
        org_id, user_a_id = seeded_org_user
        user_b = User(
            organization_id=org_id,
            email="hr-oauth-b@example.com",
            full_name="HR OAuth B",
            role="recruiter",
            status="active",
            is_active=True,
        )
        db_session.add(user_b)
        db_session.flush()
        user_b_id = user_b.id
        db_session.commit()

        headers_a = auth_headers(org_id, user_a_id)
        headers_b = auth_headers(org_id, user_b_id)
        status_a = client.get("/api/v1/hr/google/status", headers=headers_a).json()
        status_b = client.get("/api/v1/hr/google/status", headers=headers_b).json()
        assert status_a["connected"] is False
        assert status_b["connected"] is False

        connect_a = client.get("/api/v1/hr/google/connect", headers=headers_a).json()
        connect_b = client.get("/api/v1/hr/google/connect", headers=headers_b).json()
        url_a = urlparse(connect_a["authorize_url"])
        url_b = urlparse(connect_b["authorize_url"])
        state_a = parse_qs(url_a.query)["state"][0]
        state_b = parse_qs(url_b.query)["state"][0]
        assert parse_qs(url_a.query)["prompt"] == ["consent select_account"]
        assert parse_qs(url_b.query)["prompt"] == ["consent select_account"]
        assert state_a != state_b

        rows = list(db_session.scalars(select(HRGoogleOAuthState)))
        state_hashes = {row.user_id: row.token_hash for row in rows}
        assert state_hashes[user_a_id] != state_a
        assert state_hashes[user_b_id] != state_b

        payloads = {
            "code-a": ("access-a", "refresh-a", "google-a@example.com"),
            "code-b": ("access-b", "refresh-b", "google-b@example.com"),
        }
        monkeypatch.setattr(
            GoogleOAuthService,
            "exchange_code",
            lambda self, code: {
                "access_token": payloads[code][0],
                "refresh_token": payloads[code][1],
                "expires_in": 3600,
            },
        )
        monkeypatch.setattr(
            GoogleOAuthService,
            "fetch_userinfo",
            lambda self, token: {
                "email": next(
                    value[2] for value in payloads.values() if value[0] == token
                )
            },
        )

        for code, state in (("code-a", state_a), ("code-b", state_b)):
            response = client.get(
                "/api/v1/hr/google/callback",
                params={"code": code, "state": state},
                follow_redirects=False,
            )
            assert "google=connected" in response.headers["location"]

        db_session.expire_all()
        connection_a = db_session.scalar(
            select(HRGoogleConnection).where(HRGoogleConnection.user_id == user_a_id)
        )
        connection_b = db_session.scalar(
            select(HRGoogleConnection).where(HRGoogleConnection.user_id == user_b_id)
        )
        assert connection_a is not None and connection_a.google_email == "google-a@example.com"
        assert connection_b is not None and connection_b.google_email == "google-b@example.com"
        assert connection_a.access_token_encrypted != connection_b.access_token_encrypted
        assert decrypt_secret(connection_a.access_token_encrypted) == "access-a"
        assert decrypt_secret(connection_b.access_token_encrypted) == "access-b"

        status_a = client.get("/api/v1/hr/google/status", headers=headers_a).json()
        status_b = client.get("/api/v1/hr/google/status", headers=headers_b).json()
        assert status_a["google_email"] == "google-a@example.com"
        assert status_b["google_email"] == "google-b@example.com"
        disconnected = client.delete("/api/v1/hr/google/disconnect", headers=headers_a)
        assert disconnected.status_code == 200
        status_a = client.get("/api/v1/hr/google/status", headers=headers_a).json()
        assert status_a["connected"] is False
        still_connected_b = client.get("/api/v1/hr/google/status", headers=headers_b).json()
        assert still_connected_b["connected"] is True
        assert still_connected_b["google_email"] == "google-b@example.com"

    def test_unauthenticated_callback_success_persists_tokens(self, client, db_session, seeded_org_user, oauth_settings, monkeypatch):
        org_id, user_id = seeded_org_user
        service = GoogleOAuthService()
        state = service.create_state(db_session, organization_id=org_id, user_id=user_id)
        db_session.commit()

        monkeypatch.setattr(GoogleOAuthService, "exchange_code", lambda self, code: {
            "access_token": "access-token-value",
            "refresh_token": "refresh-token-value",
            "expires_in": 3600,
            "scope": "openid email https://www.googleapis.com/auth/calendar.events",
        })
        monkeypatch.setattr(GoogleOAuthService, "fetch_userinfo", lambda self, access_token: {"email": "hr-google@example.com"})

        # No auth headers: Google redirect callback
        resp = client.get(
            "/api/v1/hr/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        location = resp.headers.get("location", "")
        assert location.startswith("http://localhost:5174/interviews/availability")
        assert "google=connected" in location

        db_session.expire_all()
        conn = db_session.scalar(select(HRGoogleConnection).where(
            HRGoogleConnection.organization_id == org_id,
            HRGoogleConnection.user_id == user_id,
        ))
        assert conn is not None
        assert conn.status == "connected"
        assert conn.google_email == "hr-google@example.com"
        # tokens are encrypted at rest (not stored as plaintext)
        assert conn.access_token_encrypted != "access-token-value"
        assert conn.refresh_token_encrypted and conn.refresh_token_encrypted != "refresh-token-value"

        state_row = db_session.scalar(select(HRGoogleOAuthState).where(HRGoogleOAuthState.user_id == user_id))
        assert state_row is not None and state_row.used_at is not None

    def test_invalid_state_rejected(self, client, db_session, seeded_org_user, oauth_settings):
        org_id, user_id = seeded_org_user
        resp = client.get(
            "/api/v1/hr/google/callback",
            params={"code": "auth-code", "state": "not-a-real-state"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "google=error" in resp.headers.get("location", "")
        db_session.expire_all()
        conn = db_session.scalar(select(HRGoogleConnection).where(HRGoogleConnection.user_id == user_id))
        assert conn is None

    def test_expired_state_rejected(self, client, db_session, seeded_org_user, oauth_settings):
        org_id, user_id = seeded_org_user
        service = GoogleOAuthService()
        state = service.create_state(db_session, organization_id=org_id, user_id=user_id)
        db_session.commit()
        row = db_session.scalar(select(HRGoogleOAuthState).where(HRGoogleOAuthState.user_id == user_id))
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()

        resp = client.get(
            "/api/v1/hr/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "google=error" in resp.headers.get("location", "")
        db_session.expire_all()
        conn = db_session.scalar(select(HRGoogleConnection).where(HRGoogleConnection.user_id == user_id))
        assert conn is None

    def test_replayed_state_rejected_and_not_reusable(self, client, db_session, seeded_org_user, oauth_settings, monkeypatch):
        org_id, user_id = seeded_org_user
        service = GoogleOAuthService()
        state = service.create_state(db_session, organization_id=org_id, user_id=user_id)
        db_session.commit()

        calls = {"exchange": 0}

        def fake_exchange(self, code):
            calls["exchange"] += 1
            return {"access_token": "access-token-value", "refresh_token": "refresh-token-value", "expires_in": 3600}

        monkeypatch.setattr(GoogleOAuthService, "exchange_code", fake_exchange)
        monkeypatch.setattr(GoogleOAuthService, "fetch_userinfo", lambda self, access_token: {"email": "hr-google@example.com"})

        first = client.get(
            "/api/v1/hr/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
        assert "google=connected" in first.headers.get("location", "")
        assert calls["exchange"] == 1

        # Replay with same state must be rejected and must not trigger another exchange
        second = client.get(
            "/api/v1/hr/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
        assert "google=error" in second.headers.get("location", "")
        assert calls["exchange"] == 1

        # Consumed state must remain unusable (durable one-time consumption)
        with pytest.raises(Exception):
            GoogleOAuthService().consume_state(db_session, state)
        db_session.rollback()

    def test_failed_exchange_consumes_state_and_requires_fresh_attempt(self, client, db_session, seeded_org_user, oauth_settings, monkeypatch):
        org_id, user_id = seeded_org_user
        service = GoogleOAuthService()
        state = service.create_state(db_session, organization_id=org_id, user_id=user_id)
        db_session.commit()

        def fail_exchange(self, code):
            raise RuntimeError("boom")

        monkeypatch.setattr(GoogleOAuthService, "exchange_code", fail_exchange)

        resp = client.get(
            "/api/v1/hr/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "google=error" in resp.headers.get("location", "")

        # State consumed durably and never reusable, even though exchange failed
        with pytest.raises(Exception):
            GoogleOAuthService().consume_state(db_session, state)
        db_session.rollback()

        db_session.expire_all()
        conn = db_session.scalar(select(HRGoogleConnection).where(HRGoogleConnection.user_id == user_id))
        assert conn is None

        replay = client.get(
            "/api/v1/hr/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
        assert "google=error" in replay.headers.get("location", "")


def test_consume_state_is_atomic_under_postgres_concurrency(test_engine):
    """Two simultaneous callbacks/consumers for the same state: exactly one succeeds."""
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-specific concurrency behavior")

    SessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    raw_state = f"pg-concurrency-{uuid.uuid4()}"
    token_hash = __import__("hashlib").sha256(raw_state.encode("utf-8")).hexdigest()

    setup = SessionLocal()
    try:
        setup.add(Organization(id=org_id, name=f"PG OAuth {org_id}", status="active"))
        setup.add(
            User(
                id=user_id,
                organization_id=org_id,
                email=f"pg-oauth-{user_id}@example.com",
                full_name="PG OAuth",
                role="recruiter",
                roles=["recruiter"],
                status="active",
                is_active=True,
            )
        )
        setup.commit()
        setup.add(
            HRGoogleOAuthState(
                organization_id=org_id,
                user_id=user_id,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                used_at=None,
            )
        )
        setup.commit()
    except Exception:
        setup.rollback()
        raise
    finally:
        setup.close()

    barrier = threading.Barrier(2)
    results: list[tuple[str, object]] = []
    lock = threading.Lock()

    def worker():
        session = SessionLocal()
        try:
            barrier.wait(timeout=10)
            out = GoogleOAuthService().consume_state(session, raw_state)
            with lock:
                results.append(("ok", out))
        except Exception as exc:
            session.rollback()
            with lock:
                results.append(("err", type(exc).__name__))
        finally:
            session.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=20)
    t2.join(timeout=20)

    try:
        assert sorted(r[0] for r in results) == ["err", "ok"]
        ok = [r for r in results if r[0] == "ok"][0][1]
        assert ok == (org_id, user_id)

        verify = SessionLocal()
        try:
            state_row = verify.scalar(
                select(HRGoogleOAuthState).where(HRGoogleOAuthState.token_hash == token_hash)
            )
            assert state_row is not None and state_row.used_at is not None
        finally:
            verify.close()
    finally:
        # Cleanup committed test rows (safe test DB) to preserve cross-test isolation.
        cleanup = SessionLocal()
        try:
            cleanup.query(HRGoogleOAuthState).filter(HRGoogleOAuthState.token_hash == token_hash).delete()
            cleanup.query(HRGoogleConnection).filter(HRGoogleConnection.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.query(Organization).filter(Organization.id == org_id).delete()
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cleanup.close()
