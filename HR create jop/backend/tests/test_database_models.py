import uuid

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import Candidate, Job, JobApplication, Organization, Resume, User
from app.services.errors import ValidationError
from app.services.job_application_validation import validate_job_application_consistency


def create_core_records(db_session: Session) -> tuple[Organization, User, Job, Candidate, Resume]:
    organization = Organization(name="Acme Recruiting")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="hr@example.com",
        full_name="HR User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Candidate One",
        email="candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Backend Engineer",
        raw_description="Build backend services.",
    )
    resume = Resume(
        candidate_id=candidate.id,
        file_uri="local://resumes/candidate-one.pdf",
        original_filename="candidate-one.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
    )
    db_session.add_all([job, resume])
    db_session.flush()

    return organization, user, job, candidate, resume


def test_uuid_primary_keys_are_generated(db_session: Session) -> None:
    organization = Organization(name="UUID Org")
    db_session.add(organization)
    db_session.flush()

    assert isinstance(organization.id, uuid.UUID)


def test_organization_owns_users_jobs_and_candidates(db_session: Session) -> None:
    organization, user, job, candidate, _resume = create_core_records(db_session)

    db_session.refresh(organization)

    assert user in organization.users
    assert job in organization.jobs
    assert candidate in organization.candidates


def test_user_requires_valid_organization(db_session: Session) -> None:
    db_session.add(
        User(
            organization_id=uuid.uuid4(),
            email="missing-org@example.com",
            full_name="Missing Org",
        )
    )

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_job_requires_valid_organization(db_session: Session) -> None:
    db_session.add(Job(organization_id=uuid.uuid4(), title="Invalid Job"))

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_candidate_requires_valid_organization(db_session: Session) -> None:
    db_session.add(Candidate(organization_id=uuid.uuid4(), full_name="Invalid Candidate"))

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_resume_requires_valid_candidate(db_session: Session) -> None:
    db_session.add(Resume(candidate_id=uuid.uuid4(), file_uri="local://missing.pdf"))

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_job_application_requires_job_candidate_and_resume(db_session: Session) -> None:
    organization, _user, job, candidate, resume = create_core_records(db_session)

    invalid_application = JobApplication(
        organization_id=organization.id,
        job_id=uuid.uuid4(),
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    db_session.add(invalid_application)

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()

    db_session.rollback()
    db_session.add(
        JobApplication(
            organization_id=organization.id,
            job_id=job.id,
            candidate_id=uuid.uuid4(),
            resume_id=resume.id,
        )
    )

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()

    db_session.rollback()
    db_session.add(
        JobApplication(
            organization_id=organization.id,
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=uuid.uuid4(),
        )
    )

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_candidate_can_have_multiple_applications_for_same_job(db_session: Session) -> None:
    organization, _user, job, candidate, resume = create_core_records(db_session)

    first_application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    second_application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    db_session.add_all([first_application, second_application])
    db_session.commit()

    assert first_application.id != second_application.id
    assert len(candidate.applications) == 2
    assert len(job.applications) == 2


def test_job_application_references_selected_resume(db_session: Session) -> None:
    organization, _user, job, candidate, resume = create_core_records(db_session)

    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    db_session.add(application)
    db_session.commit()

    assert application.resume == resume
    assert application in resume.applications


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (Organization, {"name": "Bad Org", "status": "invalid"}),
        (User, {"email": "bad@example.com", "full_name": "Bad User", "status": "invalid"}),
        (Job, {"title": "Bad Job", "status": "invalid"}),
        (Candidate, {"full_name": "Bad Candidate", "status": "invalid"}),
        (Resume, {"file_uri": "local://bad.pdf", "status": "invalid"}),
        (JobApplication, {"status": "invalid"}),
    ],
)
def test_invalid_statuses_are_rejected_by_database(
    db_session: Session,
    model,
    kwargs: dict,
) -> None:
    organization, user, job, candidate, resume = create_core_records(db_session)

    defaults = {
        User: {"organization_id": organization.id},
        Job: {"organization_id": organization.id, "created_by_user_id": user.id},
        Candidate: {"organization_id": organization.id},
        Resume: {"candidate_id": candidate.id},
        JobApplication: {
            "organization_id": organization.id,
            "job_id": job.id,
            "candidate_id": candidate.id,
            "resume_id": resume.id,
        },
    }
    db_session.add(model(**(defaults.get(model, {}) | kwargs)))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_email_uniqueness_is_scoped_per_organization(db_session: Session) -> None:
    first_org = Organization(name="First Org")
    second_org = Organization(name="Second Org")
    db_session.add_all([first_org, second_org])
    db_session.flush()

    db_session.add_all(
        [
            User(
                organization_id=first_org.id,
                email="shared@example.com",
                full_name="First User",
            ),
            User(
                organization_id=second_org.id,
                email="shared@example.com",
                full_name="Second User",
            ),
        ]
    )
    db_session.commit()

    db_session.add(
        User(
            organization_id=first_org.id,
            email="shared@example.com",
            full_name="Duplicate User",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_candidate_emails_are_allowed_to_repeat(db_session: Session) -> None:
    organization = Organization(name="Candidate Org")
    db_session.add(organization)
    db_session.flush()

    db_session.add_all(
        [
            Candidate(
                organization_id=organization.id,
                full_name="First Candidate",
                email="repeat@example.com",
            ),
            Candidate(
                organization_id=organization.id,
                full_name="Second Candidate",
                email="repeat@example.com",
            ),
        ]
    )
    db_session.commit()


def test_timestamps_are_populated(db_session: Session) -> None:
    organization = Organization(name="Timestamp Org")
    db_session.add(organization)
    db_session.commit()
    db_session.refresh(organization)

    assert organization.created_at is not None
    assert organization.updated_at is not None


def test_job_application_organization_consistency_validation(db_session: Session) -> None:
    organization, _user, job, candidate, resume = create_core_records(db_session)
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.flush()

    validate_job_application_consistency(
        organization_id=organization.id,
        job=job,
        candidate=candidate,
        resume=resume,
    )

    with pytest.raises(ValidationError, match="Job must belong"):
        validate_job_application_consistency(
            organization_id=other_organization.id,
            job=job,
            candidate=candidate,
            resume=resume,
        )


def test_resume_candidate_consistency_validation(db_session: Session) -> None:
    organization, _user, job, candidate, resume = create_core_records(db_session)
    other_candidate = Candidate(organization_id=organization.id, full_name="Other Candidate")
    db_session.add(other_candidate)
    db_session.flush()

    with pytest.raises(ValidationError, match="Resume must belong"):
        validate_job_application_consistency(
            organization_id=organization.id,
            job=job,
            candidate=other_candidate,
            resume=resume,
        )
