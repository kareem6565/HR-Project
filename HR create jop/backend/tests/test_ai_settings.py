"""API integration tests for the AI-settings endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest import mock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.providers.factory import resolve_ai_config
from app.core import runtime_config
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _reset_runtime_key() -> None:
    """Fresh runtime-key state for every test; never leaks across tests."""
    runtime_config.clear_api_key()
    yield
    runtime_config.clear_api_key()


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    """Provide a synchronous test client sharing the test db_session."""
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


def auth_headers(org_id: str, user_id: str, role: str = "admin") -> dict[str, str]:
    """Return standard Bearer auth headers for tests."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=uuid.UUID(user_id),
        organization_id=uuid.UUID(org_id),
        role=role,
        token_version=1,
    )
    return {"Authorization": f"Bearer {token}"}


def bootstrap(client: httpx.Client) -> tuple[dict, dict]:
    """Create an org + admin user via internal services now that public provisioning is closed."""
    from app.services.organization_service import OrganizationService
    from app.services.user_service import UserService

    db = next(client.app.dependency_overrides[get_db]())
    org = OrganizationService().create(db, name="Settings Test")
    user = UserService().create(
        db,
        organization_id=org.id,
        email="settings@test.com",
        full_name="Settings User",
        role="admin",
    )
    db.commit()
    return {"id": str(org.id), "name": org.name}, {
        "id": str(user.id),
        "organization_id": str(user.organization_id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }


def test_get_returns_effective_config(client: httpx.Client) -> None:
    """GET /settings/ai reports the effective provider/model and never the key."""
    org, user = bootstrap(client)
    h = auth_headers(org["id"], user["id"])

    effective = resolve_ai_config(get_settings())
    resp = client.get("/api/v1/settings/ai", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == effective["provider"]
    assert body["has_api_key"] == bool(effective["api_key"])
    assert body["api_key_source"] == effective["api_key_source"]
    assert body["model"] == effective["model"]
    assert "api_key" not in body


def test_set_runtime_key_endpoint_is_disabled(client: httpx.Client) -> None:
    """POST /settings/ai/api-key is disabled to prevent cross-tenant credential mutations."""
    org, user = bootstrap(client)
    h = auth_headers(org["id"], user["id"])

    resp = client.post(
        "/api/v1/settings/ai/api-key", json={"api_key": "gh-test-key-123"}, headers=h
    )
    assert resp.status_code == 405
    assert "disabled" in resp.json()["detail"].lower()
    assert runtime_config.get_api_key() is None


def test_clear_runtime_key_endpoint_is_disabled(client: httpx.Client) -> None:
    """DELETE /settings/ai/api-key is disabled to prevent cross-tenant credential mutations."""
    org, user = bootstrap(client)
    h = auth_headers(org["id"], user["id"])

    resp = client.delete("/api/v1/settings/ai/api-key", headers=h)
    assert resp.status_code == 405
    assert "disabled" in resp.json()["detail"].lower()


def test_recruiter_cannot_access_ai_settings(client: httpx.Client) -> None:
    """Recruiters are forbidden from viewing or modifying AI settings."""
    from app.services.user_service import UserService

    org, _admin = bootstrap(client)
    db = next(client.app.dependency_overrides[get_db]())
    recruiter = UserService().create(
        db,
        organization_id=uuid.UUID(org["id"]),
        email="recruiter@test.com",
        full_name="Recruiter User",
        role="recruiter",
    )
    db.commit()
    recruiter_h = auth_headers(org["id"], str(recruiter.id), role="recruiter")

    resp = client.get("/api/v1/settings/ai", headers=recruiter_h)
    assert resp.status_code == 403

    resp = client.post("/api/v1/settings/ai/verify", json={}, headers=recruiter_h)
    assert resp.status_code == 403


@pytest.mark.skipif(
    bool(get_settings().ollama_api_key)
    or (get_settings().ai_provider == "soal" and bool(get_settings().soal_api_key)),
    reason="requires no live provider key configured (otherwise verify performs a live call)",
)
def test_verify_missing_key_returns_inline_failure(client: httpx.Client) -> None:
    """Verify without any configured key returns ok=False, not an HTTP error."""
    org, user = bootstrap(client)
    h = auth_headers(org["id"], user["id"])

    resp = client.post("/api/v1/settings/ai/verify", json={}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["message"]
    assert body["model"]


def test_verify_with_provided_key_calls_ollama(client: httpx.Client, monkeypatch) -> None:
    """Verify uses the selected provider without persisting the prospective key."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_api_key", None)
    org, user = bootstrap(client)
    h = auth_headers(org["id"], user["id"])
    fake_result = mock.Mock()
    fake_result.text = "OK"

    with mock.patch("app.api.v1.routes.ai_settings.OllamaCloudProvider") as mock_provider_cls:
        provider = mock_provider_cls.return_value
        provider.generate_text.return_value = fake_result

        resp = client.post(
            "/api/v1/settings/ai/verify", json={"api_key": "gh-probe-key"}, headers=h
        )

    mock_provider_cls.assert_called_once()
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "verified" in body["message"].lower()


def test_verify_rate_limit_reports_failure(client: httpx.Client, monkeypatch) -> None:
    """Rate limiting surfaces as ok=False with a friendly message."""
    from app.ai.providers.errors import ProviderRateLimitError
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_api_key", None)

    org, user = bootstrap(client)
    h = auth_headers(org["id"], user["id"])

    with mock.patch("app.api.v1.routes.ai_settings.OllamaCloudProvider") as mock_provider_cls:
        provider = mock_provider_cls.return_value
        provider.generate_text.side_effect = ProviderRateLimitError("quota")

        resp = client.post(
            "/api/v1/settings/ai/verify", json={"api_key": "gh-probe-key"}, headers=h
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "rate limit" in body["message"].lower()


def test_verify_provider_error_reports_failure(client: httpx.Client, monkeypatch) -> None:
    """Generic provider failures return ok=False without leaking details."""
    from app.ai.providers.errors import ProviderUnavailableError
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_api_key", None)

    org, user = bootstrap(client)
    h = auth_headers(org["id"], user["id"])

    with mock.patch("app.api.v1.routes.ai_settings.OllamaCloudProvider") as mock_provider_cls:
        provider = mock_provider_cls.return_value
        provider.generate_text.side_effect = ProviderUnavailableError("boom")

        resp = client.post(
            "/api/v1/settings/ai/verify", json={"api_key": "gh-probe-key"}, headers=h
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "provider" in body["message"].lower()


def test_verify_requires_identity(client: httpx.Client) -> None:
    """Settings endpoints reject legacy headers and require Bearer token."""
    bogus = {
        "X-User-Id": "not-a-uuid",
        "X-Organization-Id": str(uuid.uuid4()),
    }
    resp = client.get("/api/v1/settings/ai", headers=bogus)
    assert resp.status_code in (401, 422)
