"""Phase 3.7 HR decision integration tests.

Covers the explicit Human-in-the-Loop decision boundary that connects an
AI-generated CandidateEvaluation (informational only) to an authoritative,
append-only HRDecision. AI never creates a decision; only an authenticated HR
user (via DecisionService) may record one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts import requirement_key
from app.ai.providers.fake import FakeAIProvider
from app.ai.workflows import CandidateEvaluationWorkflow
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
from app.services.decision_service import DecisionService
from app.services.errors import NotFoundError, ValidationError


def create_parent_records(
    db_session: Session,
) -> tuple[Organization, User, JobApplication, JobProfile, CandidateProfile]:
    organization = Organization(name="HR Decision Integration Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="hr-decision-integration@example.com",
        full_name="HR Decision Integration User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="HR Decision Integration Candidate",
        email="hr-decision-integration-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(organization_id=organization.id, created_by_user_id=user.id, title="ML Engineer")
    resume = Resume(
        candidate_id=candidate.id, file_uri="local://resumes/hr-decision-integration.pdf"
    )
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
        profile_data={
            "title": "ML Engineer",
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "skill"},
            ],
            "skills": ["Python"],
        },
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
    application: JobApplication,
    job_profile: JobProfile,
    candidate_profile: CandidateProfile,
    recommendation: str,
) -> CandidateEvaluation:
    evaluation = CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        version_number=1,
        status="completed",
        score=Decimal("95.0"),
        recommendation=recommendation,
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


def test_create_advance_decision(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    decision = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        organization_id=organization.id,
    )
    db_session.commit()

    assert decision.id is not None
    assert decision.decision == "advance"
    assert decision.user_id == user.id
    assert decision.job_application_id == application.id


def test_create_reject_decision(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    decision = service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="reject",
        reason="Candidate did not meet core requirements.",
        organization_id=organization.id,
    )
    db_session.commit()

    assert decision.decision == "reject"
    assert decision.reason == "Candidate did not meet core requirements."


def test_create_hold_decision(db_session: Session) -> None:
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

    assert decision.decision == "hold"


def test_decision_history_is_append_only(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="hold",
        reason="First review.",
        organization_id=organization.id,
    )
    db_session.commit()
    service.create(
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
    assert decisions[-1].decision == "advance"


def test_ai_recommendation_does_not_equal_decision(db_session: Session) -> None:
    organization, user, application, jp, cp = create_parent_records(db_session)
    evaluation = create_candidate_evaluation(
        db_session,
        application=application,
        job_profile=jp,
        candidate_profile=cp,
        recommendation="advance",
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

    assert decision.decision == "reject"


def test_organization_mismatch_rejected(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    other_org = Organization(name="Other HR Org")
    db_session.add(other_org)
    db_session.commit()
    other_user = User(
        organization_id=other_org.id,
        email="other-hr@example.com",
        full_name="Other Org HR",
    )
    db_session.add(other_user)
    db_session.commit()
    service = DecisionService()

    with pytest.raises(ValidationError, match="User must belong"):
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=other_user.id,
            decision="advance",
            organization_id=organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_missing_job_application(db_session: Session) -> None:
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


def test_invalid_decision_value(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    with pytest.raises(ValidationError, match="Invalid HR decision"):
        service.create(
            db_session,
            job_application_id=application.id,
            user_id=user.id,
            decision="maybe",
            organization_id=organization.id,
        )

    assert count_rows(db_session, HRDecision) == 0


def test_evaluation_id_must_belong_to_application(db_session: Session) -> None:
    organization, user, application, jp, cp = create_parent_records(db_session)
    other_candidate = Candidate(
        organization_id=organization.id,
        full_name="Other Candidate",
        email="other-decision-candidate@example.com",
    )
    db_session.add(other_candidate)
    db_session.flush()
    other_resume = Resume(
        candidate_id=other_candidate.id,
        file_uri="local://resumes/other-decision.pdf",
    )
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
        explanation={"summary": "Other application evaluation."},
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


def test_no_autonomous_ai_decision(db_session: Session) -> None:
    assert not hasattr(DecisionService, "create_from_ai")
    assert not hasattr(DecisionService, "create_ai_decision")

    organization, _user, application, job_profile, candidate_profile = create_parent_records(
        db_session
    )
    application.resume.extracted_text = "I use Python daily."
    evidence_provider = FakeAIProvider(
        provider="fake",
        model="fake-evidence-model",
        structured_payload={
            "evidence_items": [
                {
                    "evidence_type": "matched",
                    "requirement_ref": {
                        "requirement_key": requirement_key("Python", "must_have"),
                        "skill": "Python",
                    },
                    "candidate_evidence": {"quote": "I use Python daily."},
                    "strength": "strong",
                },
            ]
        },
    )
    explanation_provider = FakeAIProvider(
        provider="fake",
        model="fake-explanation-model",
        structured_payload={
            "summary": "Candidate matches the core requirements.",
            "points": ["Python requirement is matched"],
        },
    )
    workflow = CandidateEvaluationWorkflow(
        evidence_provider=evidence_provider,
        explanation_provider=explanation_provider,
    )

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    evaluation = db_session.get(CandidateEvaluation, result.evaluation_id)
    assert evaluation is not None
    assert evaluation.score is not None
    assert count_rows(db_session, HRDecision) == 0


def test_decision_does_not_modify_evaluation(db_session: Session) -> None:
    organization, user, application, jp, cp = create_parent_records(db_session)
    evaluation = create_candidate_evaluation(
        db_session,
        application=application,
        job_profile=jp,
        candidate_profile=cp,
        recommendation="advance",
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
        decision="advance",
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


def test_decision_does_not_create_workflow_traces(db_session: Session) -> None:
    organization, user, application, _jp, _cp = create_parent_records(db_session)
    service = DecisionService()

    service.create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        reason="HR decision is deterministic, not an AI workflow.",
        organization_id=organization.id,
    )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, WorkflowStepTrace) == 0
    assert count_rows(db_session, AITrace) == 0
    assert count_rows(db_session, HRDecision) == 1
