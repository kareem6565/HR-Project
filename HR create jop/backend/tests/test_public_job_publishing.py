from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import Job, JobProfile, Organization, User
from app.services.errors import InvalidStateError, NotFoundError
from app.services.job_service import JobService


def _eligible_job(db: Session) -> Job:
    org = Organization(name="Public Company")
    user = User(organization=org, email="publisher@example.com", full_name="Publisher")
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
        profile_data={
            "requirements": [
                {"text": "Accessibility experience", "category": "must_have", "dimension": "skill"},
                {"text": "Design systems", "category": "nice_to_have", "dimension": "skill"},
                {
                    "text": "Create prototypes",
                    "category": "important",
                    "dimension": "responsibility",
                },
            ]
        },
    )
    db.add(profile)
    db.flush()
    return job


def test_publish_public_details_close_and_republish_preserve_internal_status(
    db_session: Session,
) -> None:
    service = JobService()
    job = _eligible_job(db_session)
    original_status = job.status
    published = service.publish(db_session, job_id=job.id, organization_id=job.organization_id)
    assert published.publication_status == "published"
    assert published.status == original_status == "active"
    assert len(published.public_id) == 32
    assert (
        service.publish(db_session, job_id=job.id, organization_id=job.organization_id).public_id
        == published.public_id
    )

    public = service.public_details(db_session, public_id=published.public_id)
    assert public["organization_name"] == "Public Company"
    assert public["required_qualifications"] == ["Accessibility experience"]
    assert public["responsibilities"] == ["Create prototypes"]
    assert "organization_id" not in public and "id" not in public

    closed = service.close_publication(
        db_session, job_id=job.id, organization_id=job.organization_id
    )
    assert closed.status == original_status
    assert closed.publication_status == "closed"
    assert (
        service.public_details(db_session, public_id=published.public_id)["accepting_applications"]
        is False
    )


def test_unpublished_invalid_and_cross_org_jobs_are_hidden(db_session: Session) -> None:
    job = _eligible_job(db_session)
    service = JobService()
    with pytest.raises(NotFoundError):
        service.public_details(db_session, public_id="a" * 32)
    with pytest.raises(NotFoundError):
        service.public_details(db_session, public_id="invalid")
    other = Organization(name="Other")
    db_session.add(other)
    db_session.flush()
    with pytest.raises(NotFoundError):
        service.publish(db_session, job_id=job.id, organization_id=other.id)


def test_publish_requires_approved_profile_and_close_requires_publication(
    db_session: Session,
) -> None:
    org = Organization(name="Draft Org")
    db_session.add(org)
    db_session.flush()
    job = Job(
        organization_id=org.id,
        title="Designer",
        description_text="Role",
        job_type="Full-time",
        experience="2 years",
        requirements=["Portfolio"],
        status="active",
    )
    db_session.add(job)
    db_session.flush()
    with pytest.raises(InvalidStateError, match="Approve a job requirements profile"):
        JobService().publish(db_session, job_id=job.id, organization_id=org.id)
    with pytest.raises(InvalidStateError, match="has not been published"):
        JobService().close_publication(db_session, job_id=job.id, organization_id=org.id)


def test_draft_job_cannot_be_published_even_with_approved_profile(db_session: Session) -> None:
    job = _eligible_job(db_session)
    job.status = "draft"
    db_session.flush()
    with pytest.raises(InvalidStateError, match="Activate this vacancy internally"):
        JobService().publish(db_session, job_id=job.id, organization_id=job.organization_id)
