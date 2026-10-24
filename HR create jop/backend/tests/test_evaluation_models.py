import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    HRDecision,
    Job,
    JobApplication,
    JobProfile,
    MatchEvidence,
    Organization,
    Resume,
    User,
)


def create_evaluation_parent_records(
    db_session: Session,
) -> tuple[Organization, User, JobApplication, JobProfile, CandidateProfile]:
    organization = Organization(name="Evaluation Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="reviewer@example.com",
        full_name="Reviewer User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Evaluation Candidate",
        email="evaluation-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Machine Learning Engineer",
    )
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/evaluation.pdf")
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
        profile_data={"title": "Machine Learning Engineer"},
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    candidate_profile = CandidateProfile(
        resume_id=resume.id,
        version_number=1,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python", "ML"]},
        is_current=True,
    )
    db_session.add_all([application, job_profile, candidate_profile])
    db_session.flush()

    return organization, user, application, job_profile, candidate_profile


def create_candidate_evaluation(
    db_session: Session,
) -> tuple[User, JobApplication, CandidateEvaluation]:
    _organization, user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    evaluation = CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        version_number=1,
        status="completed",
        score=Decimal("87.5"),
        recommendation="advance",
        explanation={"summary": "Strong relevant experience."},
        scoring_version="manual-test-v1",
        provenance={"source": "test"},
        is_current=True,
        completed_at=datetime.now(UTC),
    )
    db_session.add(evaluation)
    db_session.flush()

    return user, application, evaluation


def test_candidate_evaluation_can_be_created(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    evaluation = CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        version_number=1,
        status="queued",
        is_current=True,
    )
    db_session.add(evaluation)
    db_session.commit()
    db_session.refresh(evaluation)

    assert isinstance(evaluation.id, uuid.UUID)
    assert evaluation.created_at is not None
    assert evaluation.updated_at is not None
    assert evaluation.job_application == application
    assert evaluation.job_profile == job_profile
    assert evaluation.candidate_profile == candidate_profile
    assert evaluation in application.evaluations


def test_candidate_evaluation_requires_valid_parents(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )

    invalid_cases = [
        {
            "job_application_id": uuid.uuid4(),
            "job_profile_id": job_profile.id,
            "candidate_profile_id": candidate_profile.id,
        },
        {
            "job_application_id": application.id,
            "job_profile_id": uuid.uuid4(),
            "candidate_profile_id": candidate_profile.id,
        },
        {
            "job_application_id": application.id,
            "job_profile_id": job_profile.id,
            "candidate_profile_id": uuid.uuid4(),
        },
    ]

    for case in invalid_cases:
        db_session.add(
            CandidateEvaluation(
                **case,
                version_number=1,
                status="queued",
            )
        )

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()


def test_candidate_evaluation_version_is_unique_per_application(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    db_session.add_all(
        [
            CandidateEvaluation(
                job_application_id=application.id,
                job_profile_id=job_profile.id,
                candidate_profile_id=candidate_profile.id,
                version_number=1,
                status="completed",
            ),
            CandidateEvaluation(
                job_application_id=application.id,
                job_profile_id=job_profile.id,
                candidate_profile_id=candidate_profile.id,
                version_number=1,
                status="queued",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_multiple_evaluations_per_application_are_allowed(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    db_session.add_all(
        [
            CandidateEvaluation(
                job_application_id=application.id,
                job_profile_id=job_profile.id,
                candidate_profile_id=candidate_profile.id,
                version_number=1,
                status="completed",
            ),
            CandidateEvaluation(
                job_application_id=application.id,
                job_profile_id=job_profile.id,
                candidate_profile_id=candidate_profile.id,
                version_number=2,
                status="queued",
            ),
        ]
    )
    db_session.commit()

    assert len(application.evaluations) == 2


def test_invalid_evaluation_status_is_rejected(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    db_session.add(
        CandidateEvaluation(
            job_application_id=application.id,
            job_profile_id=job_profile.id,
            candidate_profile_id=candidate_profile.id,
            version_number=1,
            status="invalid",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_only_one_current_evaluation_per_application(db_session: Session) -> None:
    _organization, _user, application, job_profile, candidate_profile = (
        create_evaluation_parent_records(db_session)
    )
    db_session.add_all(
        [
            CandidateEvaluation(
                job_application_id=application.id,
                job_profile_id=job_profile.id,
                candidate_profile_id=candidate_profile.id,
                version_number=1,
                status="completed",
                is_current=True,
            ),
            CandidateEvaluation(
                job_application_id=application.id,
                job_profile_id=job_profile.id,
                candidate_profile_id=candidate_profile.id,
                version_number=2,
                status="queued",
                is_current=True,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_match_evidence_requires_valid_candidate_evaluation(db_session: Session) -> None:
    db_session.add(
        MatchEvidence(
            candidate_evaluation_id=uuid.uuid4(),
            evidence_type="matched",
        )
    )

    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()


def test_match_evidence_can_be_created_for_candidate_evaluation(db_session: Session) -> None:
    _user, _application, evaluation = create_candidate_evaluation(db_session)
    evidence = MatchEvidence(
        candidate_evaluation_id=evaluation.id,
        evidence_type="partial",
        requirement_ref={"section": "skills", "value": "Python"},
        candidate_evidence={"resume_section": "experience"},
        strength="medium",
        provenance={"source": "test"},
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)

    assert isinstance(evidence.id, uuid.UUID)
    assert evidence.created_at is not None
    assert evidence.updated_at is not None
    assert evidence.candidate_evaluation == evaluation
    assert evidence in evaluation.evidence_items


def test_invalid_evidence_type_is_rejected(db_session: Session) -> None:
    _user, _application, evaluation = create_candidate_evaluation(db_session)
    db_session.add(
        MatchEvidence(
            candidate_evaluation_id=evaluation.id,
            evidence_type="invalid",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_hr_decision_requires_valid_job_application_and_user(db_session: Session) -> None:
    user, application, _evaluation = create_candidate_evaluation(db_session)

    invalid_cases = [
        {"job_application_id": uuid.uuid4(), "user_id": user.id},
        {"job_application_id": application.id, "user_id": uuid.uuid4()},
    ]

    for case in invalid_cases:
        db_session.add(
            HRDecision(
                **case,
                decision="hold",
            )
        )

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()


def test_hr_decision_supports_append_only_history(db_session: Session) -> None:
    user, application, evaluation = create_candidate_evaluation(db_session)
    base_time = datetime.now(UTC)
    first_decision = HRDecision(
        job_application_id=application.id,
        user_id=user.id,
        candidate_evaluation_id=evaluation.id,
        decision="hold",
        reason="Needs portfolio review.",
        created_at=base_time,
    )
    second_decision = HRDecision(
        job_application_id=application.id,
        user_id=user.id,
        candidate_evaluation_id=evaluation.id,
        decision="advance",
        reason="Portfolio review complete.",
        created_at=base_time + timedelta(seconds=1),
    )
    db_session.add_all([first_decision, second_decision])
    db_session.commit()

    decisions = list(
        db_session.scalars(
            select(HRDecision)
            .where(HRDecision.job_application_id == application.id)
            .order_by(HRDecision.created_at)
        )
    )

    assert [decision.decision for decision in decisions] == ["hold", "advance"]
    assert decisions[-1].decision == "advance"
    assert first_decision in application.hr_decisions
    assert second_decision in user.hr_decisions


def test_invalid_hr_decision_value_is_rejected(db_session: Session) -> None:
    user, application, evaluation = create_candidate_evaluation(db_session)
    db_session.add(
        HRDecision(
            job_application_id=application.id,
            user_id=user.id,
            candidate_evaluation_id=evaluation.id,
            decision="invalid",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_candidate_evaluation_score_and_hr_decision_are_independent(
    db_session: Session,
) -> None:
    user, application, evaluation = create_candidate_evaluation(db_session)
    decision = HRDecision(
        job_application_id=application.id,
        user_id=user.id,
        candidate_evaluation_id=evaluation.id,
        decision="hold",
    )
    db_session.add(decision)
    db_session.commit()
    db_session.refresh(evaluation)
    db_session.refresh(decision)

    assert evaluation.score == Decimal("87.5")
    assert evaluation.recommendation == "advance"
    assert decision.decision == "hold"
    assert not hasattr(decision, "score")
    assert not hasattr(decision, "recommendation")
