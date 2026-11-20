from __future__ import annotations

import hashlib
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from resume_upload_fixtures import make_pdf_bytes
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import (
    Candidate,
    Job,
    JobApplication,
    JobDistribution,
    JobProfile,
    Organization,
    ScreeningBatchItem,
    User,
)
from app.services.job_service import JobService


@pytest.fixture()
def public_client(db_session: Session) -> Generator[TestClient, None, None]:
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def configured_test_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "application_privacy_notice_text", "TEST ONLY: process this application."
    )
    monkeypatch.setattr(settings, "application_privacy_notice_version", "local-test-v1")
    monkeypatch.setattr(settings, "application_privacy_notice_approved", False)
    monkeypatch.setattr(settings, "turnstile_required", False)
    monkeypatch.setattr(settings, "public_application_rate_limit", 20)
    monkeypatch.setattr(settings, "public_application_rate_window_seconds", 3600)


def make_published_job(db: Session, *, status: str = "published") -> Job:
    org = Organization(name="Application Test Company")
    user = User(organization=org, email=f"owner-{uuid.uuid4()}@example.test", full_name="Owner")
    db.add_all([org, user])
    db.flush()
    job = Job(
        organization_id=org.id,
        created_by_user_id=user.id,
        title="Product Designer",
        description_text="Design accessible products.",
        job_type="Full-time",
        experience="3 years",
        requirements=["Portfolio"],
        status="active",
    )
    db.add(job)
    db.flush()
    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
        profile_data={"requirements": []},
    )
    db.add(profile)
    db.flush()
    JobService().publish(db, job_id=job.id, organization_id=org.id)
    if status == "closed":
        JobService().close_publication(db, job_id=job.id, organization_id=org.id)
    elif status == "unpublished":
        job.publication_status = "unpublished"
    return job


def submit(
    client: httpx.Client, public_id: str, *, key: str = "application-key-123456", **overrides
):
    data = {
        "full_name": "  Alex Applicant  ",
        "email": "Alex@example.test ",
        "privacy_accepted": "true",
        "privacy_notice_version": "local-test-v1",
        "utm_source": "linkedin",
        "utm_medium": "social",
        "utm_campaign": "design-hiring",
    }
    data.update(
        {
            k: v
            for k, v in overrides.items()
            if k not in {"resume_file", "resume_name", "resume_type"}
        }
    )
    return client.post(
        f"/api/v1/public/jobs/{public_id}/applications",
        data=data,
        files={
            "resume": (
                overrides.get("resume_name", "resume.pdf"),
                overrides.get("resume_file", make_pdf_bytes()),
                overrides.get("resume_type", "application/pdf"),
            )
        },
        headers={"Idempotency-Key": key},
    )


def test_anonymous_submission_reuses_models_and_saves_consent_and_attribution(
    public_client: TestClient, db_session: Session
) -> None:
    job = make_published_job(db_session)
    public_id = job.public_id
    assert public_client.get(f"/api/v1/public/jobs/{public_id}").status_code == 200
    response = submit(
        public_client,
        public_id,
        phone="+1 555 123 4567",
        linkedin_url="https://www.linkedin.com/in/alex-applicant",
        github_url="https://github.com/alex-applicant",
        portfolio_url="https://portfolio.example.test/alex",
        organization_id=str(uuid.uuid4()),  # ignored; tenant is derived from Job
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["success"] is True
    assert body["application_reference"]
    assert "candidate_id" not in body and "resume_id" not in body
    application = db_session.scalar(
        select(JobApplication).where(
            JobApplication.public_reference == body["application_reference"]
        )
    )
    assert application is not None
    assert application.organization_id == job.organization_id
    assert application.job_id == job.id
    assert application.status == "created"
    assert application.source == "linkedin"
    assert application.source_medium == "social"
    assert application.source_campaign == "design-hiring"
    assert application.privacy_notice_accepted is True
    assert application.privacy_notice_version == "local-test-v1"
    assert application.privacy_notice_text == "TEST ONLY: process this application."
    assert application.privacy_notice_accepted_at is not None
    assert application.candidate.full_name == "Alex Applicant"
    assert application.candidate.email == "alex@example.test"
    assert application.public_contact_email == "Alex@example.test"
    assert application.resume.file_uri.startswith(f"resumes/{job.organization_id}/")
    item = db_session.scalar(select(ScreeningBatchItem).where(
        ScreeningBatchItem.application_id == application.id
    ))
    assert item is not None
    assert item.source == "public_application"
    assert item.status == "queued"
    assert item.job_profile_id == job.published_job_profile_id
    assert item.candidate_id == application.candidate_id
    assert item.resume_id == application.resume_id


def test_known_distribution_campaign_canonicalizes_public_application_source(
    public_client: TestClient, db_session: Session
) -> None:
    job = make_published_job(db_session)
    campaign = JobDistribution(
        organization_id=job.organization_id,
        job_id=job.id,
        approved_profile_id=job.published_job_profile_id,
        channel="wuzzuf",
        campaign_name="WUZZUF hiring share",
        tracking_key="f" * 32,
    )
    db_session.add(campaign)
    db_session.flush()

    response = submit(
        public_client,
        job.public_id,
        key="campaign-attribution-key-1234",
        utm_source="spoofed-source",
        utm_medium="spoofed-medium",
        utm_campaign=campaign.tracking_key,
    )
    assert response.status_code == 201, response.text
    application = db_session.scalar(
        select(JobApplication).where(
            JobApplication.public_reference == response.json()["application_reference"]
        )
    )
    assert application is not None
    assert application.source == "wuzzuf"
    assert application.source_medium == "job_board"
    assert application.source_campaign == campaign.tracking_key


def test_idempotent_retry_returns_same_reference_without_creating_another_application(
    public_client: TestClient, db_session: Session
) -> None:
    job = make_published_job(db_session)
    first = submit(public_client, job.public_id)
    retry = submit(public_client, job.public_id)
    assert first.status_code == retry.status_code == 201
    assert first.json()["application_reference"] == retry.json()["application_reference"]
    assert (
        db_session.scalar(select(JobApplication).where(JobApplication.job_id == job.id)) is not None
    )
    assert (
        len(db_session.scalars(select(JobApplication).where(JobApplication.job_id == job.id)).all())
        == 1
    )
    application = db_session.scalar(select(JobApplication).where(JobApplication.job_id == job.id))
    assert len(db_session.scalars(select(ScreeningBatchItem).where(
        ScreeningBatchItem.application_id == application.id
    )).all()) == 1


def test_same_email_submitted_with_new_idempotency_key_is_not_merged(
    public_client: TestClient, db_session: Session
) -> None:
    job = make_published_job(db_session)
    first = submit(public_client, job.public_id)
    second = submit(public_client, job.public_id, key="new-application-key-987654")
    assert first.status_code == second.status_code == 201
    applications = db_session.scalars(
        select(JobApplication).where(JobApplication.job_id == job.id)
    ).all()
    assert len(applications) == 2
    assert applications[0].candidate_id != applications[1].candidate_id


@pytest.mark.parametrize("publication_status", ["unpublished", "closed"])
def test_unpublished_and_closed_jobs_reject_applications(
    public_client: TestClient, db_session: Session, publication_status: str
) -> None:
    job = make_published_job(db_session, status=publication_status)
    response = submit(public_client, job.public_id)
    assert response.status_code in {404, 409}
    assert db_session.scalar(select(JobApplication).where(JobApplication.job_id == job.id)) is None


def test_invalid_public_identifier_is_not_found(public_client: TestClient) -> None:
    response = submit(public_client, "invalid")
    assert response.status_code == 404


def test_missing_resume_or_idempotency_key_is_rejected(
    public_client: TestClient, db_session: Session
) -> None:
    job = make_published_job(db_session)
    data = {
        "full_name": "Alex Applicant",
        "email": "alex@example.test",
        "privacy_accepted": "true",
        "privacy_notice_version": "local-test-v1",
    }
    missing_resume = public_client.post(
        f"/api/v1/public/jobs/{job.public_id}/applications",
        data=data,
        headers={"Idempotency-Key": "missing-resume-key-1234"},
    )
    missing_key = public_client.post(
        f"/api/v1/public/jobs/{job.public_id}/applications",
        data=data,
        files={"resume": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
    )
    assert missing_resume.status_code == 422
    assert missing_key.status_code == 422


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"full_name": " "}, "full name"),
        ({"email": "bad"}, "email"),
        ({"privacy_accepted": "false"}, "acknowledge"),
        ({"linkedin_url": "https://evil.example/user"}, "LinkedIn"),
        ({"github_url": "http://github.com/user"}, "GitHub"),
        ({"portfolio_url": "http://portfolio.example"}, "HTTPS"),
    ],
)
def test_invalid_application_fields_are_rejected(
    public_client: TestClient,
    db_session: Session,
    overrides: dict[str, str],
    message: str,
) -> None:
    job = make_published_job(db_session)
    response = submit(public_client, job.public_id, **overrides)
    assert response.status_code == 422
    assert message.lower() in response.json()["detail"].lower()


def test_unsupported_and_oversized_resumes_are_rejected(
    public_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = make_published_job(db_session)
    unsupported = submit(
        public_client, job.public_id, resume_name="resume.txt", resume_type="text/plain"
    )
    assert unsupported.status_code == 422
    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    oversized = submit(public_client, job.public_id, key="another-application-key-987654")
    assert oversized.status_code == 422
    assert oversized.json().get("code") == "TOO_LARGE"


def test_production_without_owner_approved_notice_fails_closed(
    public_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    response = public_client.get("/api/v1/public/application-config")
    assert response.status_code == 200
    assert response.json()["notice_available"] is False


def test_failed_application_flush_removes_stored_resume_and_partial_candidate(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app.services.job_application_service import JobApplicationService
    from app.services.public_application_service import PublicApplicationService

    job = make_published_job(db_session)
    monkeypatch.setattr(settings, "storage_root_dir", str(tmp_path / "private-storage"))

    def fail_create(*args, **kwargs):
        raise RuntimeError("simulated application insert failure")

    monkeypatch.setattr(JobApplicationService, "create", fail_create)
    resume_bytes = make_pdf_bytes()
    with pytest.raises(RuntimeError, match="simulated application insert failure"):
        PublicApplicationService().submit(
            db_session,
            public_id=job.public_id,
            idempotency_key="storage-cleanup-test-key-1234",
            full_name="Alex Applicant",
            email="alex@example.test",
            phone=None,
            linkedin_url=None,
            github_url=None,
            portfolio_url=None,
            resume_filename="resume.pdf",
            resume_content_type="application/pdf",
            resume_bytes=resume_bytes,
            resume_checksum=hashlib.sha256(resume_bytes).hexdigest(),
            privacy_accepted=True,
            privacy_notice_version="local-test-v1",
            turnstile_token=None,
            source=None,
            source_medium=None,
            source_campaign=None,
        )
    assert not list((tmp_path / "private-storage").rglob("*.pdf"))
    assert (
        db_session.scalar(select(Candidate).where(Candidate.organization_id == job.organization_id))
        is None
    )


def test_internally_inactive_job_rejects_public_submission(
    public_client: TestClient, db_session: Session
) -> None:
    job = make_published_job(db_session)
    job.status = "draft"
    db_session.flush()
    response = submit(public_client, job.public_id)
    assert response.status_code == 409


def test_turnstile_is_server_verified_when_required(
    public_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.public_application_service import PublicApplicationService

    job = make_published_job(db_session)
    monkeypatch.setattr(settings, "turnstile_required", True)
    monkeypatch.setattr(settings, "turnstile_secret_key", "test-secret")
    monkeypatch.setattr(
        PublicApplicationService, "verify_turnstile", staticmethod(lambda token: False)
    )
    response = submit(public_client, job.public_id, turnstile_token="invalid-token")
    assert response.status_code == 422
    assert "verification" in response.json()["detail"].lower()


def test_public_rate_limit_is_persisted_and_enforced(
    public_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = make_published_job(db_session)
    monkeypatch.setattr(settings, "public_application_rate_limit", 1)
    first = submit(public_client, job.public_id)
    second = submit(public_client, job.public_id, key="second-application-key-123456")
    assert first.status_code == 201
    assert second.status_code == 429
