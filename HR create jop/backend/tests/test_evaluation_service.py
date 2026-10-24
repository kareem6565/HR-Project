import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateProfile,
    HRDecision,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.evaluation_service import EvaluationService


def create_evaluation_parent_records(
    db_session: Session,
) -> tuple[Organization, User, JobApplication, JobProfile, CandidateProfile]:
    organization = Organization(name="Evaluation Service Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="evaluation-service@example.com",
        full_name="Evaluation User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Evaluation Candidate",
        email="eval-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(organization_id=organization.id, created_by_user_id=user.id, title="ML Engineer")
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/evaluation-service.pdf")
    db_session.add_all([job, resume])
    db_session.flush()

    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    job_profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={"title": "ML Engineer"},
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    candidate_profile = CandidateProfile(
        resume_id=resume.id,
        version_number=1,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python"]},
        is_current=True,
    )
    db_session.add_all([application, job_profile, candidate_profile])
    db_session.commit()

    return organization, user, application, job_profile, candidate_profile


def test_create_evaluation_version(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()

    evaluation = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="queued",
        score=Decimal("87.5"),
        recommendation="advance",
    )
    db_session.commit()
    db_session.refresh(evaluation)

    assert evaluation.version_number == 1
    assert evaluation.status == "queued"
    assert evaluation.score == Decimal("87.5")
    assert evaluation.recommendation == "advance"
    assert evaluation.is_current is True


def test_version_increment(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()
    service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="queued",
    )
    second = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="completed",
    )
    db_session.commit()

    assert second.version_number == 2


def test_current_rotation(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()
    first = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="queued",
    )
    second = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="completed",
    )
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.is_current is False
    assert second.is_current is True


def test_wrong_job_profile_rejected(db_session: Session) -> None:
    organization, user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    other_job = Job(organization_id=organization.id, created_by_user_id=user.id, title="Other Job")
    db_session.add(other_job)
    db_session.flush()
    wrong_job_profile = JobProfile(
        job_id=other_job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={"title": "Other Job"},
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(wrong_job_profile)
    db_session.commit()
    service = EvaluationService()

    with pytest.raises(ValidationError, match="JobProfile must belong to the JobApplication job"):
        service.create_version(
            db_session,
            job_application_id=application.id,
            job_profile_id=wrong_job_profile.id,
            candidate_profile_id=candidate_profile.id,
            status="queued",
        )


def test_wrong_candidate_profile_rejected(db_session: Session) -> None:
    organization, user, _application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    # Create a job application for a different candidate/resume so that the
    # candidate profile is unrelated to it.
    other_candidate = Candidate(
        organization_id=organization.id,
        full_name="Other Candidate",
        email="other@example.com",
    )
    db_session.add(other_candidate)
    db_session.flush()
    other_resume = Resume(candidate_id=other_candidate.id, file_uri="local://resumes/other.pdf")
    db_session.add(other_resume)
    db_session.flush()
    other_application = JobApplication(
        organization_id=organization.id,
        job_id=job_profile.job_id,
        candidate_id=other_candidate.id,
        resume_id=other_resume.id,
    )
    db_session.add(other_application)
    db_session.commit()
    service = EvaluationService()

    # Resolve the candidate profile's resume against the wrong application.
    with pytest.raises(
        ValidationError, match="CandidateProfile must belong to the JobApplication resume"
    ):
        service.create_version(
            db_session,
            job_application_id=other_application.id,
            job_profile_id=job_profile.id,
            candidate_profile_id=candidate_profile.id,
            status="queued",
        )


def test_missing_related_records_rejected(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()

    with pytest.raises(NotFoundError, match="JobApplication was not found"):
        service.create_version(
            db_session,
            job_application_id=uuid.uuid4(),
            job_profile_id=job_profile.id,
            candidate_profile_id=candidate_profile.id,
            status="queued",
        )

    with pytest.raises(NotFoundError, match="JobProfile was not found"):
        service.create_version(
            db_session,
            job_application_id=application.id,
            job_profile_id=uuid.uuid4(),
            candidate_profile_id=candidate_profile.id,
            status="queued",
        )

    with pytest.raises(NotFoundError, match="CandidateProfile was not found"):
        service.create_version(
            db_session,
            job_application_id=application.id,
            job_profile_id=job_profile.id,
            candidate_profile_id=uuid.uuid4(),
            status="queued",
        )


def test_invalid_status_rejected(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()

    with pytest.raises(ValidationError, match="Invalid candidate evaluation status"):
        service.create_version(
            db_session,
            job_application_id=application.id,
            job_profile_id=job_profile.id,
            candidate_profile_id=candidate_profile.id,
            status="invalid",
        )


def test_add_match_evidence_successfully(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()
    evaluation = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="completed",
    )
    db_session.commit()

    evidence = service.add_match_evidence(
        db_session,
        candidate_evaluation_id=evaluation.id,
        evidence_type="matched",
        requirement_ref={"skill": "Python"},
        candidate_evidence={"source": "resume"},
        strength="strong",
    )
    db_session.commit()
    db_session.refresh(evidence)

    assert evidence.evidence_type == "matched"
    assert evidence.candidate_evaluation_id == evaluation.id
    assert evidence in evaluation.evidence_items


def test_add_match_evidence_invalid_type_rejected(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()
    evaluation = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="completed",
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="Invalid match evidence type"):
        service.add_match_evidence(
            db_session,
            candidate_evaluation_id=evaluation.id,
            evidence_type="invalid",
        )


def test_organization_mismatch_rejected(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.flush()
    service = EvaluationService()

    with pytest.raises((ValidationError, NotFoundError)):
        service.create_version(
            db_session,
            job_application_id=application.id,
            job_profile_id=job_profile.id,
            candidate_profile_id=candidate_profile.id,
            status="queued",
            organization_id=other_organization.id,
        )


def test_has_hr_decision_false_when_none(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()
    evaluation = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="completed",
    )
    db_session.commit()

    assert service.has_hr_decision(db_session, evaluation_id=evaluation.id) is False


def test_has_hr_decision_true_when_decision_exists(db_session: Session) -> None:
    _organization, user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    service = EvaluationService()
    evaluation = service.create_version(
        db_session,
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        status="completed",
    )
    db_session.commit()

    db_session.add(
        HRDecision(
            job_application_id=application.id,
            user_id=user.id,
            candidate_evaluation_id=evaluation.id,
            decision="hold",
        )
    )
    db_session.commit()

    assert service.has_hr_decision(db_session, evaluation_id=evaluation.id) is True
