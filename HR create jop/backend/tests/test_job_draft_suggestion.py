"""API integration tests for the AI-assisted job creation flow.

Covers the advisory job-form auto-fill endpoint, the fixed job-profile
extraction route (draft -> awaiting_profile_review), and the profile-approval
lifecycle transition (awaiting_profile_review -> active). The AI provider is
forced to fake mode so the suite never touches a live gate.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.contracts.validation import validate_job_draft_suggestion
from app.api.v1.routes.job_drafts import (
    _clamp_suggestion_payload,
    _clamp_text,
    _derive_suggestion_payload,
)
from app.core.database import get_db
from app.main import app
from app.models import Job, Organization, User
from app.models.job_profile import JobProfile
from app.services.errors import ValidationError


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


def auth_headers(org_id: str, user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id, "X-Organization-Id": org_id}


def seed_org_user(db_session: Session) -> tuple[Organization, User]:
    organization = Organization(name="Job Creation API Org")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.id,
        email="job-creation-api@example.com",
        full_name="Job Creation API User",
    )
    db_session.add(user)
    db_session.commit()
    return organization, user


def create_job(client: httpx.Client, headers: dict[str, str], **overrides) -> dict:
    body = {
        "title": "Backend Engineer",
        "raw_description": (
            "Backend Engineer\nEngineering, remote, full-time.\n"
            "5+ years experience.\nSkills: Python, FastAPI, PostgreSQL"
        ),
        "status": "draft",
        **overrides,
    }
    resp = client.post("/api/v1/jobs", headers=headers, json=body)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class TestJobDraftSuggestionContract:
    def test_validates_and_normalizes_suggestion(self) -> None:
        suggestion = validate_job_draft_suggestion(
            {
                "title": "  Lead   Engineer  ",
                "department": "Engineering",
                "experience": "5+ years",
                "requirements": ["  Python  ", "Python", " "],
                "required_skills": ["FastAPI", " FastAPI  ", "SQL", "SQL"],
            }
        )
        assert suggestion.title == "Lead Engineer"
        assert suggestion.department == "Engineering"
        assert suggestion.experience == "5+ years"
        assert suggestion.requirements == ["Python"]
        assert suggestion.required_skills == ["FastAPI", "SQL"]

    def test_unknown_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_job_draft_suggestion({"title": "Engineer", "confidence": 0.9, "score": 87})

    def test_blank_text_fields_become_none(self) -> None:
        suggestion = validate_job_draft_suggestion({"title": "   "})
        assert suggestion.title is None


# ---------------------------------------------------------------------------
# Advisory auto-fill endpoint
# ---------------------------------------------------------------------------


class TestSuggestJobForm:
    def test_requires_identity_headers(self, client: httpx.Client) -> None:
        resp = client.post(
            "/api/v1/jobs/ai/suggest-form",
            json={"raw_description": "Backend Engineer"},
        )
        assert resp.status_code in (401, 422)

    def test_rejects_empty_description(self, client: httpx.Client, db_session: Session) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))
        resp = client.post(
            "/api/v1/jobs/ai/suggest-form", headers=headers, json={"raw_description": ""}
        )
        assert resp.status_code == 422

    def test_returns_deterministic_advisory_suggestions(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))

        resp = client.post(
            "/api/v1/jobs/ai/suggest-form",
            headers=headers,
            json={
                "raw_description": (
                    "Backend Engineer\nEngineering team, fully remote, contract.\n"
                    "5+ years experience required.\nSkills: Python, FastAPI, PostgreSQL\n"
                    "- Design APIs\n- Write tests"
                )
            },
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["title"] == "Backend Engineer"
        assert body["department"] == "engineering"
        assert body["location"] == "Remote"
        assert body["job_type"] == "Contract"
        assert body["experience"] == "5+ years"
        assert body["required_skills"] == ["Python", "FastAPI", "PostgreSQL"]
        assert body["requirements"] == ["Design APIs", "Write tests"]
        assert "schema_version" in body

    def test_is_strictly_advisory_no_persistence(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))

        resp = client.post(
            "/api/v1/jobs/ai/suggest-form",
            headers=headers,
            json={"raw_description": "Product Designer, hybrid."},
        )
        assert resp.status_code == 200
        assert db_session.query(Job).count() == 0
        assert db_session.query(JobProfile).count() == 0


# ---------------------------------------------------------------------------
# Oversized AI output clamping
# ---------------------------------------------------------------------------


class TestClampSuggestionPayload:
    def test_clamps_oversized_text_on_word_boundary(self) -> None:
        long_experience = (
            "Proven experience with distributed systems, microservices, event-driven architecture"
        )
        clamped = _clamp_text(long_experience, 100)
        assert clamped is not None
        assert len(clamped) <= 100
        assert "distributed systems" in clamped

    def test_short_and_empty_values_pass_through(self) -> None:
        assert _clamp_text("5+ years", 100) == "5+ years"
        assert _clamp_text(None, 100) is None

    def test_hard_cut_when_no_word_boundary(self) -> None:
        assert len(_clamp_text("x" * 120, 100)) == 100

    def test_clamps_each_string_field_to_its_column_limit(self) -> None:
        clamped = _clamp_suggestion_payload(
            {
                "title": "S" * 300,
                "department": "D" * 150,
                "location": "L" * 150,
                "job_type": "J" * 80,
                "experience": "E" * 150,
            }
        )
        assert len(clamped["title"]) == 255
        assert len(clamped["department"]) == 100
        assert len(clamped["location"]) == 100
        assert len(clamped["job_type"]) == 50
        assert len(clamped["experience"]) == 100

    def test_truncates_oversized_lists(self) -> None:
        clamped = _clamp_suggestion_payload(
            {
                "requirements": [f"req-{i}" for i in range(60)],
                "required_skills": [f"skill-{i}" for i in range(80)],
            }
        )
        assert len(clamped["requirements"]) == 50
        assert len(clamped["required_skills"]) == 50

    def test_non_dict_payload_passes_through(self) -> None:
        assert _clamp_suggestion_payload(None) is None

    def test_endpoint_returns_clamped_suggestion_instead_of_422(
        self, client: httpx.Client, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))

        payload = _derive_suggestion_payload(
            "Backend Engineer, engineering, remote, 5+ years. Python, FastAPI"
        )
        payload["experience"] = (
            "Proven experience with distributed systems, microservices, event-driven "
            "architecture, and observability tooling across many platforms"
        )
        payload["required_skills"] = [f"Skill-{i}" for i in range(70)]
        monkeypatch.setattr(
            "app.api.v1.routes.job_drafts._derive_suggestion_payload", lambda _raw: payload
        )

        resp = client.post(
            "/api/v1/jobs/ai/suggest-form",
            headers=headers,
            json={
                "raw_description": (
                    "Backend Engineer, engineering, remote, 5+ years. Python, FastAPI"
                )
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["experience"]) <= 100
        assert len(body["required_skills"]) == 50


# ---------------------------------------------------------------------------
# Extract route + lifecycle transition
# ---------------------------------------------------------------------------


class TestExtractJobProfile:
    def test_extract_moves_draft_job_to_awaiting_profile_review(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))
        job = create_job(client, headers)

        resp = client.post(f"/api/v1/jobs/{job['id']}/extract-profile", headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["profile_id"]
        assert body["workflow_run_id"]
        assert body["version_number"] == 1

        job_detail = client.get(f"/api/v1/jobs/{job['id']}", headers=headers)
        assert job_detail.json()["status"] == "awaiting_profile_review"

        profiles = client.get(f"/api/v1/jobs/{job['id']}/profiles", headers=headers)
        assert len(profiles.json()) == 1
        assert profiles.json()[0]["status"] == "draft"
        assert profiles.json()[0]["source"] == "ai_extracted"

    def test_extract_requires_raw_description(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))
        job = create_job(client, headers, raw_description=None)

        resp = client.post(f"/api/v1/jobs/{job['id']}/extract-profile", headers=headers)
        assert resp.status_code == 422

    def test_extract_requires_identity_headers(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        resp = client.post(f"/api/v1/jobs/{uuid.uuid4()}/extract-profile")
        assert resp.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Approve route + active transition
# ---------------------------------------------------------------------------


class TestApproveJobProfileTransition:
    def test_approve_moves_awaiting_profile_review_to_active(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))
        job = create_job(client, headers)

        extraction = client.post(f"/api/v1/jobs/{job['id']}/extract-profile", headers=headers)
        assert extraction.status_code == 201
        profile_id = extraction.json()["profile_id"]

        approved = client.post(f"/api/v1/job-profiles/{profile_id}/approve", headers=headers)
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        job_detail = client.get(f"/api/v1/jobs/{job['id']}", headers=headers)
        assert job_detail.json()["status"] == "active"

    def test_approve_does_not_flip_plain_draft_job(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        organization, user = seed_org_user(db_session)
        headers = auth_headers(str(organization.id), str(user.id))
        job = create_job(client, headers)
        assert job["status"] == "draft"

        profile = client.post(
            f"/api/v1/jobs/{job['id']}/profiles",
            headers=headers,
            json={
                "status": "draft",
                "source": "hr_created",
                "profile_data": {"title": job["title"], "requirements": []},
            },
        )
        assert profile.status_code == 201

        approved = client.post(
            f"/api/v1/job-profiles/{profile.json()['id']}/approve", headers=headers
        )
        assert approved.status_code == 200

        job_detail = client.get(f"/api/v1/jobs/{job['id']}", headers=headers)
        assert job_detail.json()["status"] == "draft"
