from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts.job_profile import requirement_key
from app.api.v1.schemas.job_distributions import JobDistributionCreate
from app.core.database import get_db
from app.main import app
from app.models import Job, JobDistributionView, JobProfile, Organization, User
from app.services.errors import InvalidStateError
from app.services.job_distribution_service import JobDistributionService
from app.services.job_service import JobService


def _auth(user: User) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        token_version=user.token_version,
    )
    return {"Authorization": f"Bearer {token}"}


def _published_job(db: Session) -> tuple[Job, User]:
    organization = Organization(name="Distribution Test Company")
    user = User(
        organization=organization,
        email=f"publisher-{uuid.uuid4()}@example.test",
        full_name="Publisher",
        role="admin",
    )
    db.add_all([organization, user])
    db.flush()
    required = {
        "text": "Experience with Python",
        "category": "must_have",
        "dimension": "technical_skill",
    }
    preferred = {
        "text": "Experience with cloud platforms",
        "category": "nice_to_have",
        "dimension": "technical_skill",
    }
    required["key"] = requirement_key(required["text"], required["category"])
    preferred["key"] = requirement_key(preferred["text"], preferred["category"])
    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Backend Engineer",
        description_text="Build and maintain backend services.",
        job_type="Full-time",
        work_mode="hybrid",
        location="Cairo",
        experience="3 years",
        requirements=["Experience with Python"],
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
        profile_data={
            "summary": "Build reliable services for customer workflows.",
            "requirements": [required, preferred],
        },
    )
    db.add(profile)
    db.flush()
    JobService().publish(db, job_id=job.id, organization_id=organization.id)
    return job, user


@contextmanager
def _client(db: Session) -> Generator[TestClient, None, None]:
    db.bind = db.connection()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def test_distribution_uses_only_approved_profile_and_records_shared_status(
    db_session: Session,
) -> None:
    job, user = _published_job(db_session)
    with _client(db_session) as client:
        headers = _auth(user)
        created = client.post(
            f"/api/v1/jobs/{job.id}/distributions",
            headers=headers,
            json={"channel": "linkedin", "campaign_name": "Backend hiring"},
        )
        assert created.status_code == 201, created.text
        campaign = created.json()
        assert campaign["approved_profile_id"] == str(job.published_job_profile_id)
        assert campaign["status"] == "draft"

        generated = client.post(
            f"/api/v1/job-distributions/{campaign['id']}/generate", headers=headers
        )
        assert generated.status_code == 200, generated.text
        post_text = generated.json()["post_text"]
        assert "Backend Engineer" in post_text
        assert "Experience with Python" in post_text
        assert "Required:" in post_text
        assert "Preferred:" in post_text

        missing_review = client.post(
            f"/api/v1/job-distributions/{campaign['id']}/mark-shared",
            headers=headers,
            json={"hr_reviewed": False},
        )
        assert missing_review.status_code == 422
        saved = client.patch(
            f"/api/v1/job-distributions/{campaign['id']}",
            headers=headers,
            json={"post_text": post_text + "\nEdited by HR"},
        )
        assert saved.status_code == 200
        shared = client.post(
            f"/api/v1/job-distributions/{campaign['id']}/mark-shared",
            headers=headers,
            json={"hr_reviewed": True, "external_post_url": "https://www.linkedin.com/feed/"},
        )
        assert shared.status_code == 200, shared.text
        assert shared.json()["status"] == "shared"
        assert shared.json()["hr_reviewed_at"]
        assert shared.json()["external_post_url"] == "https://www.linkedin.com/feed/"
        immutable = client.patch(
            f"/api/v1/job-distributions/{campaign['id']}",
            headers=headers,
            json={"post_text": "change"},
        )
        assert immutable.status_code == 409


def test_distribution_and_analytics_are_organization_scoped(db_session: Session) -> None:
    job, owner = _published_job(db_session)
    other_org = Organization(name="Other Distribution Company")
    other_user = User(
        organization=other_org,
        email=f"other-{uuid.uuid4()}@example.test",
        full_name="Other recruiter",
        role="recruiter",
    )
    db_session.add_all([other_org, other_user])
    db_session.flush()

    with _client(db_session) as client:
        create_other = client.post(
            f"/api/v1/jobs/{job.id}/distributions",
            headers=_auth(other_user),
            json={"channel": "facebook", "campaign_name": "Cross org"},
        )
        assert create_other.status_code == 404
        assert client.get("/api/v1/distribution-analytics", headers=_auth(other_user)).json() == {
            "range_days": 30,
            "campaigns": [],
            "sources": [],
        }

        own = client.post(
            f"/api/v1/jobs/{job.id}/distributions",
            headers=_auth(owner),
            json={"channel": "wuzzuf", "campaign_name": "WUZZUF campaign"},
        )
        assert own.status_code == 201
        campaign_key = own.json()["tracking_key"]
        public_url = f"/api/v1/public/jobs/{job.public_id}?utm_campaign={campaign_key}"
        assert client.get(public_url).status_code == 200
        assert client.get(public_url).status_code == 200
        assert (
            len(
                db_session.scalars(
                    select(JobDistributionView).where(
                        JobDistributionView.distribution_id == uuid.UUID(own.json()["id"])
                    )
                ).all()
            )
            == 2
        )
        analytics = client.get("/api/v1/distribution-analytics?range_days=30", headers=_auth(owner))
        assert analytics.status_code == 200, analytics.text
        assert analytics.json()["campaigns"][0]["views"] == 2
        assert analytics.json()["campaigns"][0]["channel"] == "wuzzuf"


def test_distribution_requires_published_approved_job_and_valid_campaign(
    db_session: Session,
) -> None:
    job, user = _published_job(db_session)
    job.publication_status = "closed"
    db_session.flush()
    with pytest.raises(InvalidStateError, match="Publish an active job"):
        JobDistributionService().create(
            db_session,
            job_id=job.id,
            organization_id=job.organization_id,
            user_id=user.id,
            body=JobDistributionCreate(channel="other", campaign_name="Test"),
        )

    job.publication_status = "published"
    profile = db_session.get(JobProfile, job.published_job_profile_id)
    profile.status = "superseded"
    db_session.flush()
    with pytest.raises(InvalidStateError, match="approved profile"):
        JobDistributionService().create(
            db_session,
            job_id=job.id,
            organization_id=job.organization_id,
            user_id=user.id,
            body=JobDistributionCreate(channel="other", campaign_name="Test"),
        )
