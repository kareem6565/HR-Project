import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import Candidate, Organization, Resume
from app.services.candidate_profile_service import CandidateProfileService
from app.services.errors import NotFoundError, ValidationError


def create_resume_parent_records(db_session: Session) -> tuple[Organization, Candidate, Resume]:
    organization = Organization(name="Candidate Profile Org")
    db_session.add(organization)
    db_session.flush()

    candidate = Candidate(
        organization_id=organization.id,
        full_name="Candidate Profile Candidate",
        email="candidate-profile@example.com",
    )
    db_session.add(candidate)
    db_session.flush()

    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/candidate-profile.pdf")
    db_session.add(resume)
    db_session.flush()

    return organization, candidate, resume


def test_create_first_version(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    service = CandidateProfileService()

    profile = service.create_version(
        db_session,
        resume_id=resume.id,
        status="extracted",
        source="ai_extracted",
        profile_data={"skills": ["Python"]},
    )
    db_session.commit()

    assert profile.version_number == 1
    assert profile.status == "extracted"
    assert profile.is_current is True
    assert profile.profile_data == {"skills": ["Python"]}


def test_version_increment(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    service = CandidateProfileService()

    service.create_version(
        db_session,
        resume_id=resume.id,
        status="extracted",
        source="ai_extracted",
        profile_data={"skills": ["Python"]},
    )
    second = service.create_version(
        db_session,
        resume_id=resume.id,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python", "SQL"]},
    )
    db_session.commit()

    assert second.version_number == 2


def test_current_rotation_on_create(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    service = CandidateProfileService()

    first = service.create_version(
        db_session,
        resume_id=resume.id,
        status="extracted",
        source="ai_extracted",
        profile_data={"skills": ["Python"]},
    )
    second = service.create_version(
        db_session,
        resume_id=resume.id,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python", "SQL"]},
    )
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.is_current is False
    assert second.is_current is True


def test_organization_mismatch_rejected(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.flush()
    service = CandidateProfileService()

    with pytest.raises((ValidationError, NotFoundError)):
        service.create_version(
            db_session,
            resume_id=resume.id,
            status="extracted",
            source="ai_extracted",
            profile_data={"skills": ["Python"]},
            organization_id=other_organization.id,
        )


def test_missing_resume_rejected(db_session: Session) -> None:
    service = CandidateProfileService()

    with pytest.raises(NotFoundError, match="Resume was not found"):
        service.create_version(
            db_session,
            resume_id=uuid.uuid4(),
            status="extracted",
            source="ai_extracted",
            profile_data={"skills": ["Python"]},
        )


def test_invalid_status_rejected(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    service = CandidateProfileService()

    with pytest.raises(ValidationError, match="Invalid candidate profile status"):
        service.create_version(
            db_session,
            resume_id=resume.id,
            status="invalid",
            source="ai_extracted",
            profile_data={"skills": ["Python"]},
        )


def test_invalid_source_rejected(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    service = CandidateProfileService()

    with pytest.raises(ValidationError, match="Invalid candidate profile source"):
        service.create_version(
            db_session,
            resume_id=resume.id,
            status="extracted",
            source="invalid",
            profile_data={"skills": ["Python"]},
        )


def test_get_list_and_current_or_latest(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    service = CandidateProfileService()
    first = service.create_version(
        db_session,
        resume_id=resume.id,
        status="extracted",
        source="ai_extracted",
        profile_data={"skills": ["Python"]},
    )
    latest = service.create_version(
        db_session,
        resume_id=resume.id,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python", "SQL"]},
    )
    db_session.commit()

    fetched = service.get_version(db_session, profile_id=first.id)
    versions = service.list_versions(db_session, resume_id=resume.id)
    current_or_latest = service.get_current_or_latest(db_session, resume_id=resume.id)

    assert fetched.id == first.id
    assert [profile.version_number for profile in versions] == [1, 2]
    assert current_or_latest.id == latest.id


def test_get_version_not_found(db_session: Session) -> None:
    service = CandidateProfileService()

    with pytest.raises(NotFoundError, match="CandidateProfile was not found"):
        service.get_version(db_session, profile_id=uuid.uuid4())


def test_previous_versions_are_preserved(db_session: Session) -> None:
    _organization, _candidate, resume = create_resume_parent_records(db_session)
    service = CandidateProfileService()
    first = service.create_version(
        db_session,
        resume_id=resume.id,
        status="extracted",
        source="ai_extracted",
        profile_data={"skills": ["Python"]},
    )
    service.create_version(
        db_session,
        resume_id=resume.id,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python", "SQL"]},
    )
    db_session.commit()
    db_session.refresh(first)

    assert first.profile_data == {"skills": ["Python"]}
    assert first.version_number == 1
