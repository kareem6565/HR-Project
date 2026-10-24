"""Tests for Prompt 1: Immediate security containment endpoints."""

from __future__ import annotations

import uuid
from starlette.testclient import TestClient

from app.main import create_app


def test_unauthenticated_organization_provisioning_is_closed() -> None:
    """POST /api/v1/organizations must be closed (404/not found) from public API."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.post("/api/v1/organizations", json={"name": "Attacker Org"})
        assert resp.status_code == 404


def test_unauthenticated_user_provisioning_is_closed() -> None:
    """POST /api/v1/organizations/{org_id}/users must be closed from public API."""
    app = create_app()
    fake_org_id = str(uuid.uuid4())
    with TestClient(app) as client:
        resp = client.post(
            f"/api/v1/organizations/{fake_org_id}/users",
            json={"email": "attacker@test.com", "full_name": "Attacker"},
        )
        assert resp.status_code in (401, 404)


def test_raw_storage_path_resume_creation_is_closed() -> None:
    """POST /api/v1/candidates/{candidate_id}/resumes must not accept client-chosen raw storage paths."""
    app = create_app()
    fake_cand_id = str(uuid.uuid4())
    with TestClient(app) as client:
        resp = client.post(
            f"/api/v1/candidates/{fake_cand_id}/resumes",
            json={"file_uri": "/etc/passwd"},
            headers={"X-User-Id": str(uuid.uuid4()), "X-Organization-Id": str(uuid.uuid4())},
        )
        # Endpoint removed: must return 404 (or 405 Method Not Allowed)
        assert resp.status_code in (404, 405)
