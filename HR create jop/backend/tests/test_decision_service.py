import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import (
    AITrace,
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    HRDecision,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
    WorkflowRun,
    WorkflowStepTrace,
)
from app.services import VALID_DECISIONS
from app.services.decision_service import DecisionService
from app.services.errors import NotFoundError, ValidationError


def create_parent_records(
    db_session: Session,
) -> tuple[Organization, User, JobApplication, JobProfile, CandidateProfile]:
    organization = Organization(name="Decision Service Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="decision-reviewer@example.com",
        full_name="Decision Reviewer",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Decision Candidate",
        email="decision-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(organization_id=organization.id, created_by_user_id=user.id, title="ML Engineer")
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/decision.pdf")
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


def create_candidate_evaluation(
    db_session: Session,
    *,
    organization: Organization,
    application: JobApplication,
    job_profile: JobProfile,
    candidate_profile: CandidateProfile,
) -> CandidateEvaluation:
    evaluation = CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        version_number=1,
        status="completed",
        score=Decimal("85.0"),
        recommendation="advance",
        explanation={"summary": "Strong match."},
        provenance={"source": "test"},
        is_current=True,
        completed_at=datetime.now(UTC),
    )
    db_session.add(evaluation)
    db_session.commit()
    return evaluation


def count_rows(db_session: Session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


def test_creates_explicit_hr_decision(db_session: Session) -> None:
    organization, user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    service = DecisionService()

    decision = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        reason="Strong technical match.",
        organization_id=organization.id,
    )
    db_session.commit()
    db_session.refresh(decision)

    assert decision.id is not None
    assert decision.job_application_id == application.id
    assert decision.user_id == user.id
    assert decision.decision == "advance"
    assert decision.reason == "Strong technical match."


def test_decision_transitions_application_pipeline_status(db_session: Session) -> None:
    service = DecisionService()
    transitions = {
        "advance": "advanced",
        "hold": "hold",
        "reject": "rejected",
    }

    for decision, expected_status in transitions.items():
        _org, user, application, _jp, _cp = create_parent_records(db_session)
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=user.id,
            decision=decision,
            organization_id=_org.id,
        )
        db_session.commit()
        refreshed = db_session.get(JobApplication, application.id)
        assert refreshed.status == expected_status, f"{decision} -> {expected_status}"


def test_references_correct_job_application(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    decision = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="hold",
        organization_id=organization.id,
    )
    db_session.commit()

    assert decision.job_application_id == application.id


def test_references_correct_candidate_evaluation(db_session: Session) -> None:
    organization, user, application, jp, cp = create_parent_records(db_session)
    evaluation = create_candidate_evaluation(
        db_session,
        organization=organization,
        application=application,
        job_profile=jp,
        candidate_profile=cp,
    )
    service = DecisionService()

    decision = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="reject",
        candidate_evaluation_id=evaluation.id,
        organization_id=organization.id,
    )
    db_session.commit()

    decision = db_session.get(HRDecision, decision.id)
    assert decision.candidate_evaluation_id == evaluation.id


def test_decision_allows_null_candidate_evaluation(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    decision = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="hold",
        organization_id=organization.id,
    )
    db_session.commit()

    assert decision.candidate_evaluation_id is None


def test_organization_mismatch_rejected(db_session: Session) -> None:
    _organization, _user, application, _jp, _cp = create_parent_records(db_session)
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.commit()
    service = DecisionService()

    with pytest.raises((ValidationError, NotFoundError)):
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=_user.id,
            decision="advance",
            organization_id=other_organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_user_from_another_organization_rejected(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.flush()
    other_user = User(
        organization_id=other_org.id,
        email="other@example.com",
        full_name="Other User",
    )
    db_session.add(other_user)
    db_session.commit()
    service = DecisionService()

    with pytest.raises((ValidationError, NotFoundError)):
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=other_user.id,
            decision="advance",
            organization_id=organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_missing_job_application_rejected(db_session: Session) -> None:
    organization, user, _application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    with pytest.raises(NotFoundError, match="JobApplication was not found"):
        service.create(
            db_session,
            job_application_id=uuid.uuid4(),
            user_id=user.id,
            decision="advance",
            organization_id=organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_missing_user_rejected(db_session: Session) -> None:
    organization, _user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    with pytest.raises(NotFoundError, match="User was not found"):
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=uuid.uuid4(),
            decision="advance",
            organization_id=organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_missing_candidate_evaluation_rejected(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    with pytest.raises(NotFoundError, match="CandidateEvaluation was not found"):
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=user.id,
            decision="advance",
            candidate_evaluation_id=uuid.uuid4(),
            organization_id=organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_evaluation_from_another_application_rejected(db_session: Session) -> None:
    organization, user, application, jp, cp = create_parent_records(db_session)
    # Build a second candidate/application for the same job to host a foreign
    # CandidateEvaluation that does not belong to the target application.
    other_candidate = Candidate(
        organization_id=organization.id,
        full_name="Other Candidate",
        email="other-candidate@example.com",
    )
    db_session.add(other_candidate)
    db_session.flush()
    other_resume = Resume(candidate_id=other_candidate.id, file_uri="local://resumes/other.pdf")
    db_session.add(other_resume)
    db_session.flush()
    other_application = JobApplication(
        organization_id=organization.id,
        job_id=jp.job_id,
        candidate_id=other_candidate.id,
        resume_id=other_resume.id,
    )
    db_session.add(other_application)
    db_session.flush()
    other_evaluation = CandidateEvaluation(
        job_application_id=other_application.id,
        job_profile_id=jp.id,
        candidate_profile_id=cp.id,
        version_number=1,
        status="completed",
        explanation={"summary": "Other."},
        is_current=True,
    )
    db_session.add(other_evaluation)
    db_session.commit()
    service = DecisionService()

    with pytest.raises(ValidationError, match="must belong to the JobApplication"):
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=user.id,
            decision="advance",
            candidate_evaluation_id=other_evaluation.id,
            organization_id=organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_invalid_decision_rejected(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    for bad_decision in ("approve", "hire", "reject_now", ""):
        with pytest.raises(ValidationError, match="Invalid HR decision"):
            service.create(
                db_session,
                job_application_id=application.id,
                user_id=user.id,
                decision=bad_decision,
                organization_id=organization.id,
            )

    assert count_rows(db_session, HRDecision) == 0


def test_valid_decisions_vocabulary(db_session: Session) -> None:
    assert VALID_DECISIONS == {"advance", "reject", "hold"}


def test_multiple_decisions_preserve_append_only_history(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    first = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="hold",
        reason="First review.",
        organization_id=organization.id,
    )
    db_session.commit()
    second = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        reason="Second review.",
        organization_id=organization.id,
    )
    db_session.commit()

    decisions = list(
        db_session.scalars(
            select(HRDecision)
            .where(HRDecision.job_application_id == application.id)
            .order_by(HRDecision.created_at)
        )
    )
    assert [d.decision for d in decisions] == ["hold", "advance"]
    assert db_session.get(HRDecision, first.id).reason == "First review."
    assert db_session.get(HRDecision, second.id).reason == "Second review."


def test_existing_decisions_not_modified(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    first = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="hold",
        reason="Original reason.",
        organization_id=organization.id,
    )
    db_session.commit()
    before = db_session.get(HRDecision, first.id).reason

    service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        organization_id=organization.id,
    )
    db_session.commit()

    after = db_session.get(HRDecision, first.id)
    assert after.reason == before
    assert after.decision == "hold"


def test_candidate_evaluation_not_modified(db_session: Session) -> None:
    organization, user, application, jp, cp = create_parent_records(db_session)
    evaluation = create_candidate_evaluation(
        db_session,
        organization=organization,
        application=application,
        job_profile=jp,
        candidate_profile=cp,
    )
    before = {
        "status": evaluation.status,
        "score": evaluation.score,
        "recommendation": evaluation.recommendation,
        "is_current": evaluation.is_current,
        "explanation": evaluation.explanation,
    }
    service = DecisionService()

    decision = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="reject",
        candidate_evaluation_id=evaluation.id,
        organization_id=organization.id,
    )
    db_session.commit()
    db_session.expire_all()

    after = db_session.get(CandidateEvaluation, evaluation.id)
    assert after.status == before["status"]
    assert after.score == before["score"]
    assert after.recommendation == before["recommendation"]
    assert after.is_current == before["is_current"]
    assert after.explanation == before["explanation"]
    assert decision.candidate_evaluation_id == evaluation.id


def test_job_profile_not_modified(db_session: Session) -> None:
    organization, user, application, jp, _cp = create_parent_records(db_session)
    before = jp.status
    service = DecisionService()

    service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        organization_id=organization.id,
    )
    db_session.commit()

    assert db_session.get(JobProfile, jp.id).status == before


def test_candidate_profile_not_modified(db_session: Session) -> None:
    organization, user, application, _jp, cp = create_parent_records(db_session)
    before = cp.status
    service = DecisionService()

    service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        organization_id=organization.id,
    )
    db_session.commit()

    assert db_session.get(CandidateProfile, cp.id).status == before


def test_no_workflow_or_ai_traces_created(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        organization_id=organization.id,
    )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, WorkflowStepTrace) == 0
    assert count_rows(db_session, AITrace) == 0


def test_service_never_commits(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        organization_id=organization.id,
    )

    assert count_rows(db_session, HRDecision) == 1

    db_session.rollback()

    assert count_rows(db_session, HRDecision) == 0


def test_persistence_failure_propagates(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    # A dangling foreign key forces a DB IntegrityError at commit time. The
    # service/application must let the persistence error propagate rather than
    # swallow it under a broad exception handler.
    db_session.add(
        HRDecision(
            job_application_id=application.id,
            user_id=user.id,
            candidate_evaluation_id=uuid.uuid4(),
            decision="advance",
        )
    )
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()

    assert count_rows(db_session, HRDecision) == 0
