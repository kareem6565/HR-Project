import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import Job, JobProfile, Organization, User
from app.services.errors import InvalidStateError, NotFoundError, ValidationError
from app.services.job_profile_service import JobProfileService


def create_job_parent_records(db_session: Session) -> tuple[Organization, User, Job]:
    organization = Organization(name="Job Profile Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="job-profile-approver@example.com",
        full_name="Job Profile Approver",
    )
    db_session.add(user)
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Data Engineer",
    )
    db_session.add(job)
    db_session.flush()

    return organization, user, job


def create_profile_version(service, db_session, job, **overrides) -> JobProfile:
    kwargs = {
        "db": db_session,
        "job_id": job.id,
        "status": "draft",
        "source": "ai_extracted",
        "profile_data": {"title": "Data Engineer"},
        **overrides,
    }
    return service.create_version(**kwargs)


def test_create_first_version(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()

    profile = create_profile_version(service, db_session, job)
    db_session.commit()

    assert profile.version_number == 1
    assert profile.status == "draft"
    assert profile.is_current is True
    assert profile.profile_data == {"title": "Data Engineer"}


def test_version_increment(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()

    create_profile_version(service, db_session, job, profile_data={"title": "A"})
    second = create_profile_version(
        service, db_session, job, source="hr_edited", profile_data={"title": "B"}
    )
    db_session.commit()

    assert second.version_number == 2


def test_current_rotation_on_create(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()

    first = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    second = create_profile_version(
        service, db_session, job, source="hr_edited", profile_data={"title": "B"}
    )
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.is_current is False
    assert second.is_current is True


def test_organization_mismatch_rejected(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.flush()
    service = JobProfileService()

    with pytest.raises((ValidationError, NotFoundError)):
        create_profile_version(service, db_session, job, organization_id=other_organization.id)


def test_missing_job_rejected(db_session: Session) -> None:
    service = JobProfileService()

    with pytest.raises(NotFoundError, match="Job was not found"):
        service.create_version(
            db_session,
            job_id=uuid.uuid4(),
            status="draft",
            source="ai_extracted",
            profile_data={"title": "Data Engineer"},
        )


def test_invalid_status_rejected(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()

    with pytest.raises(ValidationError, match="Invalid job profile status"):
        create_profile_version(service, db_session, job, status="invalid")


def test_invalid_source_rejected(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()

    with pytest.raises(ValidationError, match="Invalid job profile source"):
        create_profile_version(service, db_session, job, source="invalid")


def test_get_version(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    created = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    db_session.commit()

    fetched = service.get_version(db_session, profile_id=created.id)

    assert fetched.id == created.id


def test_get_version_not_found(db_session: Session) -> None:
    service = JobProfileService()

    with pytest.raises(NotFoundError, match="JobProfile was not found"):
        service.get_version(db_session, profile_id=uuid.uuid4())


def test_list_versions(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    create_profile_version(service, db_session, job, profile_data={"title": "A"})
    create_profile_version(
        service, db_session, job, source="hr_edited", profile_data={"title": "B"}
    )
    db_session.commit()

    versions = service.list_versions(db_session, job_id=job.id)

    assert [profile.version_number for profile in versions] == [1, 2]
    assert [profile.profile_data for profile in versions] == [
        {"title": "A"},
        {"title": "B"},
    ]


def test_current_or_latest_returns_current_when_present(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    create_profile_version(service, db_session, job, profile_data={"title": "A"})
    latest = create_profile_version(
        service, db_session, job, source="hr_edited", profile_data={"title": "B"}
    )
    db_session.commit()

    result = service.get_current_or_latest(db_session, job_id=job.id)

    assert result.id == latest.id


def test_current_or_latest_falls_back_to_latest_when_none_current(
    db_session: Session,
) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    first = create_profile_version(
        service, db_session, job, profile_data={"title": "A"}, make_current=False
    )
    second = create_profile_version(
        service,
        db_session,
        job,
        source="hr_edited",
        profile_data={"title": "B"},
        make_current=False,
    )
    db_session.commit()

    result = service.get_current_or_latest(db_session, job_id=job.id)

    assert result.id == second.id
    assert result.id != first.id


def test_current_or_latest_returns_none_when_no_versions(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()

    result = service.get_current_or_latest(db_session, job_id=job.id)

    assert result is None


def test_approve_happy_path(db_session: Session) -> None:
    _organization, user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    draft = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    db_session.commit()

    approved = service.approve(db_session, profile_id=draft.id, approved_by_user_id=user.id)
    db_session.commit()
    db_session.refresh(approved)

    assert approved.status == "approved"
    assert approved.is_current is True
    assert approved.approved_by_user_id == user.id
    assert approved.approved_at is not None


def test_approval_metadata_recorded(db_session: Session) -> None:
    _organization, user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    draft = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    db_session.commit()
    fixed_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    approved = service.approve(
        db_session,
        profile_id=draft.id,
        approved_by_user_id=user.id,
        approved_at=fixed_time,
    )
    db_session.commit()

    assert approved.status == "approved"
    assert approved.approved_at.replace(tzinfo=UTC) == fixed_time


def test_current_rotation_on_approval(db_session: Session) -> None:
    _organization, user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    first = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    second = create_profile_version(
        service, db_session, job, source="hr_edited", profile_data={"title": "B"}
    )
    db_session.commit()

    # Approve the older version; it must become current and the newer one must yield.
    approved = service.approve(db_session, profile_id=first.id, approved_by_user_id=user.id)
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(approved)

    assert first.is_current is True
    assert second.is_current is False
    assert approved.is_current is True
    assert approved.id == first.id


def test_cross_organization_approver_rejected(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.flush()
    other_user = User(
        organization_id=other_organization.id,
        email="other@example.com",
        full_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()
    service = JobProfileService()
    draft = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    db_session.commit()

    with pytest.raises((ValidationError, NotFoundError)):
        service.approve(db_session, profile_id=draft.id, approved_by_user_id=other_user.id)


def test_missing_approver_rejected(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    draft = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    db_session.commit()

    with pytest.raises(NotFoundError, match="Approving user was not found"):
        service.approve(db_session, profile_id=draft.id, approved_by_user_id=uuid.uuid4())


def test_double_approval_rejected(db_session: Session) -> None:
    _organization, user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    draft = create_profile_version(service, db_session, job, profile_data={"title": "A"})
    db_session.commit()
    service.approve(db_session, profile_id=draft.id, approved_by_user_id=user.id)
    db_session.commit()

    with pytest.raises(InvalidStateError, match="already approved"):
        service.approve(db_session, profile_id=draft.id, approved_by_user_id=user.id)


def test_hr_edit_creates_new_draft_version(db_session: Session) -> None:
    _organization, _user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    create_profile_version(service, db_session, job, profile_data={"title": "A"})
    db_session.commit()

    hr_edit = create_profile_version(
        service, db_session, job, source="hr_edited", profile_data={"title": "B"}
    )
    db_session.commit()

    assert hr_edit.version_number == 2
    assert hr_edit.status == "draft"
    assert hr_edit.source == "hr_edited"
    assert hr_edit.is_current is True


def test_approved_profile_data_is_never_mutated_by_later_versions(db_session: Session) -> None:
    _organization, user, job = create_job_parent_records(db_session)
    service = JobProfileService()
    approved = create_profile_version(
        service, db_session, job, source="hr_created", profile_data={"title": "A"}
    )
    service.approve(db_session, profile_id=approved.id, approved_by_user_id=user.id)
    db_session.commit()

    edited = create_profile_version(
        service, db_session, job, source="hr_edited", profile_data={"title": "B"}
    )
    service.approve(db_session, profile_id=edited.id, approved_by_user_id=user.id)
    db_session.commit()
    db_session.refresh(approved)
    db_session.refresh(edited)

    assert approved.status == "approved"
    assert approved.approved_at is not None
    assert approved.profile_data == {"title": "A"}
    assert edited.status == "approved"
    assert edited.profile_data == {"title": "B"}
