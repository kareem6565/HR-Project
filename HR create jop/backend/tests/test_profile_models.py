import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Candidate, CandidateProfile, Job, JobProfile, Organization, Resume, User


def create_profile_parent_records(db_session: Session) -> tuple[Organization, User, Job, Resume]:
    organization = Organization(name="Profile Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="approver@example.com",
        full_name="Approver User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Profile Candidate",
        email="profile-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Data Engineer",
    )
    resume = Resume(
        candidate_id=candidate.id,
        file_uri="local://resumes/profile-candidate.pdf",
    )
    db_session.add_all([job, resume])
    db_session.flush()

    return organization, user, job, resume


def test_job_profile_can_be_created_for_job(db_session: Session) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)
    profile_data = {"title": "Data Engineer", "must_have_skills": ["Python"]}
    raw_input_snapshot = {"raw_description": "Python data pipelines"}
    provenance = {"schema_version": "job-profile-v1"}

    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="draft",
        source="ai_extracted",
        raw_input_snapshot=raw_input_snapshot,
        profile_data=profile_data,
        provenance=provenance,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    assert isinstance(profile.id, uuid.UUID)
    assert profile.created_at is not None
    assert profile.updated_at is not None
    assert profile.profile_data == profile_data
    assert profile.raw_input_snapshot == raw_input_snapshot
    assert profile.provenance == provenance
    assert profile.job == job
    assert profile in job.profiles


def test_candidate_profile_can_be_created_for_resume(db_session: Session) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    profile_data = {"full_name": "Profile Candidate", "skills": ["Python"]}
    provenance = {"schema_version": "candidate-profile-v1"}

    profile = CandidateProfile(
        resume_id=resume.id,
        version_number=1,
        status="extracted",
        source="ai_extracted",
        profile_data=profile_data,
        provenance=provenance,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    assert isinstance(profile.id, uuid.UUID)
    assert profile.created_at is not None
    assert profile.updated_at is not None
    assert profile.profile_data == profile_data
    assert profile.provenance == provenance
    assert profile.resume == resume
    assert profile in resume.profiles


def test_multiple_job_profile_versions_are_preserved(db_session: Session) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)
    first_profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="draft",
        source="ai_extracted",
        profile_data={"title": "Data Engineer"},
    )
    second_profile = JobProfile(
        job_id=job.id,
        version_number=2,
        status="draft",
        source="hr_edited",
        profile_data={"title": "Senior Data Engineer"},
    )
    db_session.add_all([first_profile, second_profile])
    db_session.commit()

    assert {profile.version_number for profile in job.profiles} == {1, 2}
    assert first_profile.profile_data == {"title": "Data Engineer"}


def test_multiple_candidate_profile_versions_are_preserved(db_session: Session) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    first_profile = CandidateProfile(
        resume_id=resume.id,
        version_number=1,
        status="extracted",
        source="ai_extracted",
        profile_data={"skills": ["Python"]},
    )
    second_profile = CandidateProfile(
        resume_id=resume.id,
        version_number=2,
        status="current",
        source="hr_corrected",
        profile_data={"skills": ["Python", "SQL"]},
    )
    db_session.add_all([first_profile, second_profile])
    db_session.commit()

    assert {profile.version_number for profile in resume.profiles} == {1, 2}
    assert first_profile.profile_data == {"skills": ["Python"]}


def test_duplicate_job_profile_version_fails(db_session: Session) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)
    db_session.add_all(
        [
            JobProfile(
                job_id=job.id,
                version_number=1,
                status="draft",
                source="ai_extracted",
                profile_data={"title": "One"},
            ),
            JobProfile(
                job_id=job.id,
                version_number=1,
                status="draft",
                source="hr_edited",
                profile_data={"title": "Two"},
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_candidate_profile_version_fails(db_session: Session) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    db_session.add_all(
        [
            CandidateProfile(
                resume_id=resume.id,
                version_number=1,
                status="extracted",
                source="ai_extracted",
                profile_data={"skills": ["Python"]},
            ),
            CandidateProfile(
                resume_id=resume.id,
                version_number=1,
                status="current",
                source="hr_corrected",
                profile_data={"skills": ["SQL"]},
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("status", ["draft", "approved", "superseded"])
def test_valid_job_profile_statuses_are_accepted(db_session: Session, status: str) -> None:
    _organization, user, job, _resume = create_profile_parent_records(db_session)

    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status=status,
        source="hr_created",
        profile_data={"title": "Data Engineer"},
        approved_by_user_id=user.id if status == "approved" else None,
        approved_at=datetime.now(UTC) if status == "approved" else None,
    )
    db_session.add(profile)
    db_session.commit()


def test_invalid_job_profile_status_is_rejected(db_session: Session) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)
    db_session.add(
        JobProfile(
            job_id=job.id,
            version_number=1,
            status="invalid",
            source="ai_extracted",
            profile_data={"title": "Data Engineer"},
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("source", ["ai_extracted", "hr_edited", "hr_created"])
def test_valid_job_profile_sources_are_accepted(db_session: Session, source: str) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)

    db_session.add(
        JobProfile(
            job_id=job.id,
            version_number=1,
            status="draft",
            source=source,
            profile_data={"title": "Data Engineer"},
        )
    )
    db_session.commit()


def test_invalid_job_profile_source_is_rejected(db_session: Session) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)
    db_session.add(
        JobProfile(
            job_id=job.id,
            version_number=1,
            status="draft",
            source="invalid",
            profile_data={"title": "Data Engineer"},
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_approved_job_profile_requires_approval_metadata(db_session: Session) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)
    db_session.add(
        JobProfile(
            job_id=job.id,
            version_number=1,
            status="approved",
            source="hr_created",
            profile_data={"title": "Data Engineer"},
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_approved_job_profile_can_store_approving_user(db_session: Session) -> None:
    _organization, user, job, _resume = create_profile_parent_records(db_session)
    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={"title": "Data Engineer"},
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.commit()

    assert profile.approved_by == user
    assert profile in user.approved_job_profiles


def test_only_one_current_job_profile_per_job(db_session: Session) -> None:
    _organization, _user, job, _resume = create_profile_parent_records(db_session)
    db_session.add_all(
        [
            JobProfile(
                job_id=job.id,
                version_number=1,
                status="draft",
                source="ai_extracted",
                profile_data={"title": "One"},
                is_current=True,
            ),
            JobProfile(
                job_id=job.id,
                version_number=2,
                status="draft",
                source="hr_edited",
                profile_data={"title": "Two"},
                is_current=True,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_different_jobs_can_have_current_profiles(db_session: Session) -> None:
    organization, user, first_job, _resume = create_profile_parent_records(db_session)
    second_job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Analytics Engineer",
    )
    db_session.add(second_job)
    db_session.flush()

    db_session.add_all(
        [
            JobProfile(
                job_id=first_job.id,
                version_number=1,
                status="draft",
                source="ai_extracted",
                profile_data={"title": "Data Engineer"},
                is_current=True,
            ),
            JobProfile(
                job_id=second_job.id,
                version_number=1,
                status="draft",
                source="ai_extracted",
                profile_data={"title": "Analytics Engineer"},
                is_current=True,
            ),
        ]
    )
    db_session.commit()


@pytest.mark.parametrize("status", ["extracted", "current", "superseded", "failed"])
def test_valid_candidate_profile_statuses_are_accepted(db_session: Session, status: str) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    db_session.add(
        CandidateProfile(
            resume_id=resume.id,
            version_number=1,
            status=status,
            source="ai_extracted",
            profile_data={"skills": ["Python"]},
        )
    )
    db_session.commit()


def test_invalid_candidate_profile_status_is_rejected(db_session: Session) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    db_session.add(
        CandidateProfile(
            resume_id=resume.id,
            version_number=1,
            status="invalid",
            source="ai_extracted",
            profile_data={"skills": ["Python"]},
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("source", ["ai_extracted", "hr_corrected", "system_extracted"])
def test_valid_candidate_profile_sources_are_accepted(db_session: Session, source: str) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    db_session.add(
        CandidateProfile(
            resume_id=resume.id,
            version_number=1,
            status="extracted",
            source=source,
            profile_data={"skills": ["Python"]},
        )
    )
    db_session.commit()


def test_invalid_candidate_profile_source_is_rejected(db_session: Session) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    db_session.add(
        CandidateProfile(
            resume_id=resume.id,
            version_number=1,
            status="extracted",
            source="invalid",
            profile_data={"skills": ["Python"]},
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_only_one_current_candidate_profile_per_resume(db_session: Session) -> None:
    _organization, _user, _job, resume = create_profile_parent_records(db_session)
    db_session.add_all(
        [
            CandidateProfile(
                resume_id=resume.id,
                version_number=1,
                status="current",
                source="ai_extracted",
                profile_data={"skills": ["Python"]},
                is_current=True,
            ),
            CandidateProfile(
                resume_id=resume.id,
                version_number=2,
                status="current",
                source="hr_corrected",
                profile_data={"skills": ["Python", "SQL"]},
                is_current=True,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_different_resumes_can_have_current_profiles(db_session: Session) -> None:
    organization, _user, _job, first_resume = create_profile_parent_records(db_session)
    second_candidate = Candidate(organization_id=organization.id, full_name="Second Candidate")
    db_session.add(second_candidate)
    db_session.flush()
    second_resume = Resume(candidate_id=second_candidate.id, file_uri="local://resumes/second.pdf")
    db_session.add(second_resume)
    db_session.flush()

    db_session.add_all(
        [
            CandidateProfile(
                resume_id=first_resume.id,
                version_number=1,
                status="current",
                source="ai_extracted",
                profile_data={"skills": ["Python"]},
                is_current=True,
            ),
            CandidateProfile(
                resume_id=second_resume.id,
                version_number=1,
                status="current",
                source="ai_extracted",
                profile_data={"skills": ["SQL"]},
                is_current=True,
            ),
        ]
    )
    db_session.commit()
