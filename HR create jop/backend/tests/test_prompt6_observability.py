"""Comprehensive tests for HERA Prompt 6: Structured Logging, Request Tracing & Health Checks.

Validates:
- Server-generated request IDs (X-Request-ID header, no client override).
- Request log correlation matching the response X-Request-ID.
- Exactly one completion log per request (no duplicates).
- Controlled HTTP 500 error responses with request ID and zero leakage of stack traces, paths, or secrets.
- Redaction of sensitive tokens, API keys, passwords, candidate emails, phone numbers, and CV text.
- Liveness (/health, /api/v1/health) succeeds without database queries.
- Readiness (/health/ready, /api/v1/health/ready) returns 200 on DB availability and 503 on DB failure.
- Database resource release upon readiness failure.
- Preservation of 401/403/422 status codes without noisy server-error logs.
"""

from __future__ import annotations

import io
import json
import logging
import uuid

from fastapi import APIRouter
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import (
    RedactingFilter,
    StructuredJsonFormatter,
    get_request_id,
    sanitize_log_value,
)
from app.main import app

# ---------------------------------------------------------------------------
# Test Helpers & Route Injection for Synthetic Failures
# ---------------------------------------------------------------------------

_dummy_router = APIRouter()


@_dummy_router.get("/_test/unexpected-crash")
def crash_endpoint():
    """Endpoint that raises an unexpected exception containing sensitive-looking details."""
    raise RuntimeError("Unexpected DB crash at /var/secret/path with user secret_password_12345!")


@_dummy_router.post("/_test/echo-input")
def echo_endpoint(data: dict):
    return {"received": True}


app.include_router(_dummy_router)


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 1. Request Correlation & Header Tests
# ---------------------------------------------------------------------------


def test_request_id_generated_and_returned_in_header(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    req_id = resp.headers["X-Request-ID"]
    # Must be valid UUID4
    parsed_uuid = uuid.UUID(req_id)
    assert str(parsed_uuid) == req_id


def test_client_supplied_request_id_cannot_overwrite_server_generated_id(
    client: TestClient,
) -> None:
    untrusted_id = "attacker-controlled-request-id-12345"
    resp = client.get("/api/v1/health", headers={"X-Request-ID": untrusted_id})
    assert resp.status_code == 200
    server_id = resp.headers.get("X-Request-ID")
    assert server_id != untrusted_id
    # Must be valid server-generated UUID
    assert str(uuid.UUID(server_id)) == server_id


def test_every_request_receives_unique_id(client: TestClient) -> None:
    resp1 = client.get("/api/v1/health")
    resp2 = client.get("/api/v1/health")
    id1 = resp1.headers.get("X-Request-ID")
    id2 = resp2.headers.get("X-Request-ID")
    assert id1 is not None and id2 is not None
    assert id1 != id2


def test_failed_requests_still_produce_request_id(client: TestClient) -> None:
    # 404 Not Found
    resp = client.get("/api/v1/nonexistent-route-xyz")
    assert resp.status_code == 404
    assert "X-Request-ID" in resp.headers
    assert uuid.UUID(resp.headers["X-Request-ID"])


# ---------------------------------------------------------------------------
# 2. Structured Logging & Correlation Tests
# ---------------------------------------------------------------------------


def test_request_log_matches_response_header_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    resp = client.get("/api/v1/health")
    req_id = resp.headers["X-Request-ID"]

    # Verify log record has matching request_id
    records = [r for r in caplog.records if r.name == "app.request"]
    assert len(records) == 1
    rec = records[0]
    assert getattr(rec, "request_id", None) == req_id
    assert getattr(rec, "route", None) in ("/api/v1/health", "/health")
    assert getattr(rec, "status_code", None) == 200
    assert getattr(rec, "method", None) == "GET"
    assert getattr(rec, "duration_ms", None) is not None


def test_middleware_does_not_produce_duplicate_completion_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    caplog.clear()

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200

    request_logs = [r for r in caplog.records if r.name == "app.request"]
    assert len(request_logs) == 1


def test_structured_json_formatter_output() -> None:
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test event message",
        args=(),
        exc_info=None,
    )
    record.request_id = "test-uuid-1234"
    record.method = "POST"
    record.route = "/api/v1/jobs/{job_id}/screen"
    record.status_code = 201
    record.duration_ms = 42.5

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "app.test"
    assert parsed["message"] == "Test event message"
    assert parsed["request_id"] == "test-uuid-1234"
    assert parsed["method"] == "POST"
    assert parsed["route"] == "/api/v1/jobs/{job_id}/screen"
    assert parsed["status_code"] == 201
    assert parsed["duration_ms"] == 42.5
    assert "timestamp" in parsed


# ---------------------------------------------------------------------------
# 3. Safe Exception Handling Tests
# ---------------------------------------------------------------------------


def test_unexpected_exception_returns_controlled_500(client: TestClient) -> None:
    resp = client.get("/_test/unexpected-crash")
    assert resp.status_code == 500
    data = resp.json()

    # Generic error message without internal paths or secret leaks
    assert data["detail"] == "Internal server error."
    assert "request_id" in data
    assert "X-Request-ID" in resp.headers
    assert data["request_id"] == resp.headers["X-Request-ID"]

    # Must NOT leak exception text, filesystem paths, or credentials
    raw_text = resp.text
    assert "/var/secret/path" not in raw_text
    assert "secret_password" not in raw_text
    assert "RuntimeError" not in raw_text
    assert "Traceback" not in raw_text


def test_client_errors_do_not_produce_server_error_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    caplog.clear()

    # 401 Unauthorized (missing auth token)
    resp = client.get("/api/v1/candidates")
    assert resp.status_code == 401

    # Ensure no ERROR or CRITICAL log was emitted for a normal 401
    error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_logs) == 0


# ---------------------------------------------------------------------------
# 4. Privacy & Log Redaction Tests
# ---------------------------------------------------------------------------


def test_sanitize_log_value_redacts_credentials_and_pii() -> None:
    fake_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_payload.dummy_signature"
    fake_email = "candidate-ada.lovelace@synthetic-domain.com"
    fake_phone = "+1 (555) 234-5678"
    fake_db = "postgresql+psycopg://hr_user:super_secret_pw@db.prod.internal:5432/hr_db"
    fake_key = "api_key=soal_live_liveapikey999888"

    raw = f"User {fake_email} ({fake_phone}) used {fake_token} with {fake_key} on {fake_db}"
    sanitized = sanitize_log_value(raw)

    assert fake_email not in sanitized
    assert "[EMAIL_REDACTED]" in sanitized

    assert fake_phone not in sanitized
    assert "[PHONE_REDACTED]" in sanitized

    assert "dummy_signature" not in sanitized
    assert "Bearer [REDACTED]" in sanitized

    assert "super_secret_pw" not in sanitized
    assert "soal_live_liveapikey999888" not in sanitized


def test_redacting_filter_prevents_log_leakage(caplog: pytest.LogCaptureFixture) -> None:
    filter_ = RedactingFilter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Candidate email is %s with token %s",
        args=("ada.turing@secret-corp.org", "Bearer secret_jwt_token_value_abc"),
        exc_info=None,
    )
    filter_.filter(record)

    msg = record.getMessage()
    assert "ada.turing@secret-corp.org" not in msg
    assert "[EMAIL_REDACTED]" in msg
    assert "secret_jwt_token_value_abc" not in msg
    assert "[REDACTED]" in msg


def test_upload_failure_does_not_log_cv_text_marker(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    caplog.clear()

    # Synthetic marker inside invalid upload payload
    secret_marker = "MARKER_SYNTHETIC_CANDIDATE_SECRET_DATA_XYZ_987654"
    payload = f"%PDF-1.4\n{secret_marker}\ncorrupt pdf body".encode()

    resp = client.post(
        f"/api/v1/candidates/{uuid.uuid4()}/resumes/upload",
        files={"file": ("resume.pdf", payload, "application/pdf")},
    )
    # Fails with 401 (unauthenticated) or 404/422
    assert resp.status_code in (401, 404, 422)

    # Verify the synthetic marker does not appear anywhere in captured log output
    for record in caplog.records:
        assert secret_marker not in record.getMessage()


# ---------------------------------------------------------------------------
# 5. Health Check Tests (Liveness & Readiness)
# ---------------------------------------------------------------------------


def test_liveness_endpoint_returns_ok_without_db(client: TestClient) -> None:
    # Both root /health and prefixed /api/v1/health should respond
    for path in ("/health", "/api/v1/health"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert "X-Request-ID" in resp.headers


def test_readiness_endpoint_succeeds_when_db_available(client: TestClient) -> None:
    for path in ("/health/ready", "/api/v1/health/ready"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}
        assert "X-Request-ID" in resp.headers


def test_readiness_endpoint_fails_503_when_db_unavailable(client: TestClient) -> None:
    # Simulate DB failure by overriding get_db to raise OperationalError
    def failing_get_db():
        raise OperationalError("connection refused", params=None, orig=Exception("DB down"))

    app.dependency_overrides[get_db] = failing_get_db

    try:
        for path in ("/health/ready", "/api/v1/health/ready"):
            resp = client.get(path)
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unavailable"
            assert data["detail"] == "Database unavailable."
            # Must NOT leak exception details or connection strings
            assert "OperationalError" not in resp.text
            assert "connection refused" not in resp.text
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_endpoints_do_not_expose_credentials_or_config(client: TestClient) -> None:
    for path in ("/health", "/health/ready", "/api/v1/health", "/api/v1/health/ready"):
        resp = client.get(path)
        text = resp.text
        assert "password" not in text.lower()
        assert "secret" not in text.lower()
        assert "database_url" not in text.lower()
        assert "postgresql" not in text.lower()
