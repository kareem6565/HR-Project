from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.providers.fake import FakeAIProvider
from app.ai.workflows import JobProfileExtractionWorkflow
from app.models import Job, JobProfile, Organization, User
from app.services.errors import InvalidStateError, NotFoundError, ValidationError
from app.services.job_profile_service import JobProfileService
from app.services.job_service import JobService


def _org(db: Session, name: str) -> Organization:
    org = Organization(name=name)
    db.add(org)
    db.flush()
    return org


def _vacancy(db: Session, org: Organization, **kwargs) -> Job:
    job = Job(organization_id=org.id, title="Data Engineer", **kwargs)
    db.add(job)
    db.flush()
    return job


def test_create_replays_same_organization_idempotency_key(db_session: Session) -> None:
    organization = _org(db_session, "Idempotent Org")
    service = JobService()

    first = service.create(
        db_session,
        organization_id=organization.id,
        title="Data Engineer",
        idempotency_key="request-123",
    )
    replay = service.create(
        db_session,
        organization_id=organization.id,
        title="Different retry payload",
        idempotency_key="request-123",
    )

    assert replay.id == first.id
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1


def test_idempotency_keys_are_scoped_to_organization(db_session: Session) -> None:
    org_a = _org(db_session, "First Org")
    org_b = _org(db_session, "Second Org")
    service = JobService()

    first = service.create(
        db_session, organization_id=org_a.id, title="Engineer", idempotency_key="same-key"
    )
    second = service.create(
        db_session, organization_id=org_b.id, title="Engineer", idempotency_key="same-key"
    )

    assert first.id != second.id
    with pytest.raises(NotFoundError):
        service.get(db_session, job_id=first.id, organization_id=org_b.id)


def test_new_vacancies_must_start_as_drafts(db_session: Session) -> None:
    organization = _org(db_session, "Draft Org")
    with pytest.raises(ValidationError, match="saved as drafts"):
        JobService().create(
            db_session,
            organization_id=organization.id,
            title="Engineer",
            status="active",
        )


def test_activation_lists_missing_required_vacancy_fields(db_session: Session) -> None:
    organization = _org(db_session, "Activation Org")
    job = _vacancy(db_session, organization, raw_description="", description_text="")

    with pytest.raises(ValidationError) as exc:
        JobService().validate_for_activation(db_session, job)

    message = str(exc.value)
    assert "job description" in message
    assert "employment type" in message
    assert "required experience" in message
    assert "at least one requirement" in message


def test_activation_requires_an_approved_profile(db_session: Session) -> None:
    organization = _org(db_session, "Profile Gate Org")
    user = User(
        organization_id=organization.id,
        email="profile-gate@example.com",
        full_name="Recruiter",
    )
    db_session.add(user)
    db_session.flush()
    job = _vacancy(
        db_session,
        organization,
        description_text="Build data systems.",
        job_type="Full-time",
        experience="3 years",
        requirements=["Python"],
    )
    draft = JobProfile(
        job_id=job.id,
        version_number=1,
        status="draft",
        source="hr_created",
        profile_data={"title": "Data Engineer", "requirements": []},
        is_current=True,
    )
    db_session.add(draft)
    db_session.flush()

    with pytest.raises(InvalidStateError, match="Approve a reviewed job requirements profile"):
        JobService().validate_for_activation(db_session, job)

    JobProfileService().approve(
        db_session,
        profile_id=draft.id,
        approved_by_user_id=user.id,
        organization_id=organization.id,
    )
    JobService().validate_for_activation(db_session, job)


def test_editing_draft_preserves_verified_metadata_and_marks_changes_uncertain(
    db_session: Session,
) -> None:
    organization = _org(db_session, "Profile Edit Org")
    approver = User(
        organization_id=organization.id,
        email="profile-editor@example.com",
        full_name="Profile Editor",
    )
    db_session.add(approver)
    db_session.flush()
    job = _vacancy(db_session, organization)
    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="draft",
        source="ai_extracted",
        profile_data={
            "schema_version": "1.3",
            "title": "Data Engineer",
            "requirements": [
                {
                    "key": "old",
                    "text": "Python",
                    "category": "must_have",
                    "dimension": "skill",
                    "source": "manual_description",
                    "source_quote": "Python experience required",
                    "evidence_status": "verified",
                }
            ],
            "coverage": {"certification": "unspecified"},
        },
        is_current=True,
    )
    db_session.add(profile)
    db_session.flush()

    updated = JobProfileService().update_draft(
        db_session,
        profile_id=profile.id,
        organization_id=organization.id,
        edited_by_user_id=approver.id,
        profile_data={
            **profile.profile_data,
            "requirements": [
                {
                    **profile.profile_data["requirements"][0],
                    "text": "Python and FastAPI",
                }
            ],
        },
    )

    requirement = updated.profile_data["requirements"][0]
    assert updated.id != profile.id
    assert profile.status == "superseded"
    assert profile.profile_data["requirements"][0]["text"] == "Python"
    assert updated.source == "hr_edited"
    assert requirement["text"] == "Python and FastAPI"
    assert requirement["evidence_status"] == "uncertain"
    assert requirement["edited_by_hr"] is True
    assert updated.profile_data["coverage"] == {"certification": "unspecified"}
    with pytest.raises(InvalidStateError, match="Only a draft job profile can be approved"):
        JobProfileService().approve(
            db_session,
            profile_id=profile.id,
            approved_by_user_id=approver.id,
            organization_id=organization.id,
        )


def test_extraction_uses_file_and_structured_sources_and_marks_conflicts(
    db_session: Session,
) -> None:
    organization = _org(db_session, "Extraction Inputs Org")
    job = _vacancy(
        db_session,
        organization,
        description_text="This is a part-time position requiring 5 years of experience.",
        source_file_text=(
            "Candidates must hold a CPA certification. The role expects 4 years of experience."
        ),
        source_file_sha256="a" * 64,
        job_type="Full-time",
        experience="2 years",
    )
    provider = FakeAIProvider(
        provider="fake",
        model="test-model",
        structured_payload={
            "title": "Data Engineer",
            "summary": "Data systems role",
            "requirements": [
                {
                    "text": "CPA certification",
                    "category": "must_have",
                    "dimension": "certification",
                    "source": "uploaded_file",
                    "source_quote": "Candidates must hold a CPA certification.",
                }
            ],
        },
    )

    result = JobProfileExtractionWorkflow(provider).run(
        db_session, job_id=job.id, organization_id=organization.id
    )
    profile = db_session.get(JobProfile, result.profile_id)
    data = profile.profile_data

    requirement = data["requirements"][0]
    assert requirement["source"] == "uploaded_file"
    assert requirement["evidence_status"] == "verified"
    assert data["coverage"]["certification"] == "provided"
    assert data["coverage"]["education"] == "unspecified"
    assert {item["field"] for item in data["conflicts"]} == {"employment_type", "experience"}
    experience_conflict = next(item for item in data["conflicts"] if item["field"] == "experience")
    assert [value["source"] for value in experience_conflict["values"]] == [
        "structured_specification",
        "manual_description",
        "uploaded_file",
    ]


def test_extraction_retry_key_returns_existing_profile(db_session: Session) -> None:
    organization = _org(db_session, "Extraction Idempotency Org")
    job = _vacancy(
        db_session,
        organization,
        description_text="Build data tools with Python.",
        job_type="Full-time",
        experience="3 years",
        required_skills=["Python"],
    )
    provider = FakeAIProvider(
        provider="fake",
        model="test-model",
        structured_payload={"title": "Data Engineer", "requirements": []},
    )
    workflow = JobProfileExtractionWorkflow(provider)

    first = workflow.run(
        db_session, job_id=job.id, organization_id=organization.id, request_key="extract-123"
    )
    replay = workflow.run(
        db_session, job_id=job.id, organization_id=organization.id, request_key="extract-123"
    )

    assert replay.profile_id == first.profile_id
    assert replay.workflow_run_id == first.workflow_run_id
    assert db_session.scalar(select(func.count()).select_from(JobProfile)) == 1
