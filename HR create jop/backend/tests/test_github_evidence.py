from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.providers.fake import FakeAIProvider
from app.core.database import get_db
from app.main import app
from app.models import (
    Candidate,
    GitHubEvidenceAnalysis,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
)
from app.services.github_evidence_service import GitHubEvidenceService


@pytest.fixture()
def client(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[httpx.Client, None, None]:
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_screening_worker", False)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _application(db: Session, suffix: str = "one"):
    org = Organization(name=f"GitHub Evidence Org {suffix}")
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email=f"github-hr-{suffix}@example.test",
        full_name="Evidence HR",
        role="recruiter",
    )
    candidate = Candidate(
        organization_id=org.id,
        full_name="Synthetic Candidate",
        email=f"github-candidate-{suffix}@example.test",
    )
    db.add_all([user, candidate])
    db.flush()
    job = Job(organization_id=org.id, created_by_user_id=user.id, title="Python Engineer")
    resume = Resume(candidate_id=candidate.id, file_uri=f"local://{uuid.uuid4()}.pdf")
    db.add_all([job, resume])
    db.flush()
    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={
            "title": "Python Engineer",
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "technical_skill"},
            ],
        },
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    db.add(profile)
    db.flush()
    job.published_job_profile_id = profile.id
    app_row = JobApplication(
        organization_id=org.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        github_url="https://github.com/alex",
    )
    db.add(app_row)
    db.flush()
    return org, user, app_row, profile


def _headers(org: Organization, user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id), "X-Organization-Id": str(org.id)}


def test_candidate_consent_is_required_and_analysis_is_tenant_scoped(
    client: httpx.Client, db_session: Session
) -> None:
    org, user, application, _profile = _application(db_session)
    headers = _headers(org, user)
    response = client.post(
        f"/api/v1/applications/{application.id}/github-evidence/consent-link",
        headers=headers,
        json={"repository_urls": []},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "awaiting_consent"
    token = created["consent_url"].split("#", 1)[1]

    preview = client.post(
        "/api/v1/candidate-portal/github-evidence-consent/preview", json={"token": token}
    )
    assert preview.status_code == 200
    assert "does not change an existing score" in preview.json()["consent_text"]
    assert application.github_url in preview.json()["repository_urls"]
    assert application.candidate.full_name not in preview.text

    latest = client.get(
        f"/api/v1/applications/{application.id}/github-evidence/latest", headers=headers
    )
    assert latest.status_code == 200
    assert latest.json()["status"] == "awaiting_consent"

    accepted = client.post(
        "/api/v1/candidate-portal/github-evidence-consent/respond",
        json={"token": token, "decision": "accepted", "self_attested": True},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "pending"

    other_org, other_user, *_ = _application(db_session, "other")
    cross_tenant = client.get(
        f"/api/v1/applications/{application.id}/github-evidence/latest",
        headers=_headers(other_org, other_user),
    )
    assert cross_tenant.status_code == 404


def test_github_consent_rejects_external_hosts_without_creating_record(
    client: httpx.Client, db_session: Session
) -> None:
    org, user, application, _profile = _application(db_session)
    response = client.post(
        f"/api/v1/applications/{application.id}/github-evidence/consent-link",
        headers=_headers(org, user),
        json={"repository_urls": ["https://github.com.evil.test/attacker/repo"]},
    )
    assert response.status_code == 422
    assert db_session.query(GitHubEvidenceAnalysis).count() == 0


def test_assessments_cannot_cite_uncollected_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.contracts.job_profile import JobRequirement

    job_requirement = JobRequirement(
        text="Python", category="must_have", dimension="technical_skill"
    )
    invalid = {
        "assessments": [
            {
                "requirement_key": job_requirement.key,
                "classification": "direct",
                "evidence_ids": ["invented-id"],
                "explanation": "A claimed supporting source.",
                "limitations": [],
            }
        ]
    }
    monkeypatch.setattr(
        "app.services.github_evidence_service.get_provider",
        lambda _settings: FakeAIProvider(structured_payload=invalid),
    )
    from app.services.errors import ValidationError

    with pytest.raises(ValidationError, match="not collected"):
        GitHubEvidenceService._assess(
            [job_requirement],
            [
                {
                    "evidence_id": "gh-1",
                    "kind": "readme",
                    "source_url": "https://github.com/a/b",
                    "content": {},
                    "limitation": "Indirect.",
                }
            ],
        )


def test_worker_completes_analysis_with_mocked_public_data_and_provider(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, user, application, _profile = _application(db_session, "worker")
    service = GitHubEvidenceService()
    row, token = service.create_consent_link(
        db_session,
        application_id=application.id,
        organization_id=org.id,
        actor_user_id=user.id,
        repository_urls=[],
    )
    service.respond(db_session, token=token, decision="accepted")

    observation = {
        "evidence_id": "gh-1",
        "kind": "readme",
        "source_url": "https://github.com/alex/demo/blob/main/README.md",
        "content": {"text": "A demo project."},
        "limitation": "Project documentation is indirect evidence.",
    }

    class MockGitHubClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def collect(self, _urls):
            return [observation]

    monkeypatch.setattr("app.services.github_evidence_service.GitHubPublicClient", MockGitHubClient)
    from app.ai.contracts.job_profile import JobRequirement

    req = JobRequirement(text="Python", category="must_have", dimension="technical_skill")
    provider = FakeAIProvider(
        structured_payload={
            "assessments": [
                {
                    "requirement_key": req.key,
                    "classification": "indirect",
                    "evidence_ids": ["gh-1"],
                    "explanation": "The public README describes a project using Python.",
                    "limitations": ["The README does not establish who implemented the project."],
                }
            ]
        }
    )
    monkeypatch.setattr(
        "app.services.github_evidence_service.get_provider", lambda _settings: provider
    )

    claimed_id = service.claim_next(db_session)
    assert claimed_id == row.id
    assert service.process_claimed(db_session, claimed_id) is True
    db_session.refresh(row)
    assert row.status == "completed"
    assert row.evidence == [observation]
    assert row.assessments[0]["requirement_text"] == "Python"


def test_provider_failure_is_persisted_with_a_safe_error_code(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    org, user, application, _profile = _application(db_session, "failure")
    service = GitHubEvidenceService()
    row, token = service.create_consent_link(
        db_session,
        application_id=application.id,
        organization_id=org.id,
        actor_user_id=user.id,
        repository_urls=[],
    )
    service.respond(db_session, token=token, decision="accepted")

    class MockGitHubClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def collect(self, _urls):
            return [
                {
                    "evidence_id": "gh-1",
                    "kind": "readme",
                    "source_url": "https://github.com/alex/demo",
                    "content": {"text": "Python"},
                    "limitation": "Project docs do not prove proficiency.",
                }
            ]

    monkeypatch.setattr("app.services.github_evidence_service.GitHubPublicClient", MockGitHubClient)
    monkeypatch.setattr(
        "app.services.github_evidence_service.get_provider",
        lambda _settings: FakeAIProvider(failure_kind="unavailable"),
    )
    claimed_id = service.claim_next(db_session)
    assert claimed_id == row.id
    assert service.process_claimed(db_session, claimed_id) is False
    db_session.refresh(row)
    assert row.status == "failed"
    assert row.error_code == "AI_PROVIDER_ERROR"
    assert row.evidence[0]["evidence_id"] == "gh-1"
