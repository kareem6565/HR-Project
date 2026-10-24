import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts import requirement_key
from app.ai.providers.errors import ProviderTimeoutError
from app.ai.providers.factory import get_provider
from app.ai.providers.fake import FakeAIProvider
from app.ai.workflows import InterviewQuestionGenerationWorkflow
from app.core.config import Settings
from app.models import (
    AITrace,
    Candidate,
    CandidateProfile,
    HRDecision,
    InterviewQuestion,
    InterviewQuestionSet,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
    WorkflowRun,
    WorkflowStepTrace,
)
from app.services.errors import NotFoundError, ValidationError


def create_parent_records(
    db_session: Session,
) -> tuple[Organization, User, JobApplication, JobProfile, CandidateProfile]:
    organization = Organization(name="Interview Question Generation Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="question-generation@example.com",
        full_name="Question Workflow User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Question Workflow Candidate",
        email="question-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Backend Developer",
    )
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/question-generation.pdf")
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
            "title": "Backend Developer",
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "skill"},
                {"text": "Docker", "category": "important", "dimension": "skill"},
            ],
            "skills": ["Python", "Docker"],
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
        profile_data={"skills": ["Python", "PostgreSQL"]},
        is_current=True,
    )
    db_session.add_all([application, job_profile, candidate_profile])
    db_session.commit()

    return organization, user, application, job_profile, candidate_profile


def review_guide(purpose: str, basis: str = "job_requirement", quote: str | None = None) -> dict:
    return {
        "purpose": purpose,
        "evidence_basis": basis,
        "source_quote": quote,
        "interviewer_looks_for": "A clear approach, relevant example, and validation method.",
        "evaluation_rubric": [
            "Explains the approach in a clear sequence.",
            "Uses a relevant example or trade-off.",
            "Describes how correctness would be checked.",
        ],
    }


def valid_question_set_payload() -> dict:
    return {
        "schema_version": "1.2",
        "questions": [
            {
                "category": "technical",
                "text": "Walk me through how you have used Python to build REST APIs.",
                "topic": "Python",
                "requirement_key": requirement_key("Python", "must_have"),
                "review_guide": review_guide("Explore practical Python experience."),
            },
            {
                "category": "technical",
                "text": "Describe your hands-on experience containerizing services with Docker.",
                "topic": "Docker",
                "requirement_key": requirement_key("Docker", "important"),
                "review_guide": review_guide("Explore practical Docker experience."),
            },
            {
                "category": "candidate_specific",
                "text": "Walk me through the most complex thing you built with PostgreSQL.",
                "topic": "PostgreSQL",
                "requirement_key": None,
                "review_guide": review_guide(
                    "Verify PostgreSQL experience.", "verification_question"
                ),
            },
        ]
    }


def make_workflow(
    *, payload: dict | None = None, failure=None
) -> tuple[InterviewQuestionGenerationWorkflow, FakeAIProvider]:
    provider = FakeAIProvider(
        provider="fake",
        model="fake-question-model",
        structured_payload=payload if payload is not None else valid_question_set_payload(),
        token_usage={"input_tokens": 30, "output_tokens": 20},
        latency_ms=150,
        failure=failure,
    )
    workflow = InterviewQuestionGenerationWorkflow(provider=provider)
    return workflow, provider


def count_rows(db_session: Session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


def only_one(db_session: Session, model):
    return db_session.scalar(select(model).limit(1))


def test_success_creates_generated_set_and_traces(db_session: Session) -> None:
    organization, _user, application, job_profile, candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    question_set = db_session.get(InterviewQuestionSet, result.question_set_id)
    run = db_session.get(WorkflowRun, result.workflow_run_id)
    step = db_session.get(WorkflowStepTrace, result.workflow_step_trace_id)
    trace = db_session.get(AITrace, result.ai_trace_id)

    assert result.version_number == 1
    assert question_set.status == "generated"
    assert question_set.is_current is False
    assert question_set.job_application_id == application.id
    assert question_set.generated_by == "fake:fake-question-model"
    assert run.status == "completed"
    assert step.status == "completed"
    assert step.step_name == "generate_interview_questions"
    assert trace.status == "succeeded"
    assert trace.provider == "fake"


def test_questions_persisted_in_order_with_topics(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    question_set = db_session.get(InterviewQuestionSet, result.question_set_id)
    assert len(question_set.questions) == 3
    assert [question.position for question in question_set.questions] == [0, 1, 2]
    assert question_set.questions[0].topic == "Python"
    assert question_set.questions[0].requirement_key == requirement_key("Python", "must_have")


def test_verified_cv_question_guide_is_validated_and_persisted(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    exact_quote = "Built PostgreSQL services handling 2M records."
    application.resume.extracted_text = f"Projects: {exact_quote}"
    payload = valid_question_set_payload()
    payload["questions"][2]["review_guide"] = review_guide(
        "Explore the verified PostgreSQL project experience.",
        "verified_cv_evidence",
        exact_quote,
    )
    workflow, _ = make_workflow(payload=payload)

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    question_set = db_session.get(InterviewQuestionSet, result.question_set_id)
    stored_guide = question_set.questions[2].review_guide
    assert stored_guide["evidence_basis"] == "verified_cv_evidence"
    assert stored_guide["source_quote"] == exact_quote
    assert stored_guide["source_quote"] in application.resume.extracted_text


def test_unverified_cv_question_quote_fails_without_persisting(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    application.resume.extracted_text = "Projects: Built PostgreSQL services."
    payload = valid_question_set_payload()
    payload["questions"][2]["review_guide"] = review_guide(
        "Explore a project.", "verified_cv_evidence", "Used PostgreSQL at scale."
    )
    workflow, _ = make_workflow(payload=payload)

    with pytest.raises(ValidationError, match="not found verbatim"):
        workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
    db_session.commit()

    assert count_rows(db_session, InterviewQuestionSet) == 0


def test_regeneration_creates_new_version_and_preserves_previous(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    first = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()
    second = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    first_set = db_session.get(InterviewQuestionSet, first.question_set_id)
    second_set = db_session.get(InterviewQuestionSet, second.question_set_id)
    db_session.refresh(first_set)
    db_session.refresh(second_set)

    assert first_set.version_number == 1
    assert second_set.version_number == 2
    assert first_set.status == "generated"
    assert second_set.status == "generated"


def test_requires_approved_job_profile(db_session: Session) -> None:
    organization, _user, application, job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()
    job_profile.status = "draft"
    db_session.commit()

    with pytest.raises(ValidationError, match="approved"):
        workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, AITrace) == 0
    assert count_rows(db_session, InterviewQuestionSet) == 0
    assert count_rows(db_session, InterviewQuestion) == 0


def test_requires_current_candidate_profile(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()
    candidate_profile = db_session.scalar(
        select(CandidateProfile).where(CandidateProfile.resume_id == application.resume_id).limit(1)
    )
    candidate_profile.is_current = False
    db_session.commit()

    with pytest.raises(ValidationError, match="current CandidateProfile"):
        workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, InterviewQuestionSet) == 0


def test_organization_mismatch_fails_before_traces(db_session: Session) -> None:
    _organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()
    other_organization = Organization(name="Other Org")
    db_session.add(other_organization)
    db_session.commit()

    with pytest.raises(ValidationError, match="different organization"):
        workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=other_organization.id,
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, AITrace) == 0
    assert count_rows(db_session, InterviewQuestionSet) == 0


def test_missing_job_application_fails_before_traces(db_session: Session) -> None:
    organization, _user, _application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    with pytest.raises(NotFoundError, match="JobApplication was not found"):
        workflow.run(
            db_session,
            job_application_id=uuid.uuid4(),
            organization_id=organization.id,
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, AITrace) == 0
    assert count_rows(db_session, InterviewQuestionSet) == 0


def test_provider_failure_creates_failed_traces(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow(failure=ProviderTimeoutError("timed out"))

    with pytest.raises(ProviderTimeoutError):
        workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
    db_session.commit()

    trace = only_one(db_session, AITrace)
    step = only_one(db_session, WorkflowStepTrace)
    run = only_one(db_session, WorkflowRun)
    assert trace.status == "failed"
    assert step.status == "failed"
    assert step.error_type == "ProviderTimeoutError"
    assert run.status == "failed"
    assert count_rows(db_session, InterviewQuestionSet) == 0


def test_invalid_output_creates_validation_failed_trace(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow(payload={"questions": []})

    with pytest.raises(ValidationError):
        workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
    db_session.commit()

    trace = only_one(db_session, AITrace)
    assert trace.status == "validation_failed"
    assert trace.validation_error is not None
    assert count_rows(db_session, InterviewQuestionSet) == 0


def test_no_hr_decision_is_created(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    assert count_rows(db_session, HRDecision) == 0


def test_question_key_must_exist_in_supplied_set(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    unknown_key = requirement_key("Unknown", "must_have")
    payload = {
        "schema_version": "1.2",
        "questions": [
            {
                "category": "technical",
                "text": "Question about an unknown requirement.",
                "requirement_key": unknown_key,
                "review_guide": review_guide("Explore this requirement."),
            }
        ]
    }
    workflow, _ = make_workflow(payload=payload)

    with pytest.raises(ValidationError, match="not among the requirement keys"):
        workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
    db_session.commit()

    assert count_rows(db_session, InterviewQuestionSet) == 0


def test_question_text_uses_readable_topics_not_raw_keys(db_session: Session) -> None:
    """Regression: gap/requirement topics must be readable, never raw keys."""
    organization, user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    # Force a "gap" requirement whose only representation uses an opaque ref.
    payload = {
        "schema_version": "1.2",
        "questions": [
            {
                "category": "candidate_specific",
                "text": "The role expects Python experience; the candidate lacks it.",
                "topic": "Python",
                "requirement_key": None,
                "review_guide": review_guide(
                    "Check the candidate's approach.", "verification_question"
                ),
            }
        ]
    }
    workflow, _ = make_workflow(payload=payload)

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    question_set = db_session.get(InterviewQuestionSet, result.question_set_id)
    assert question_set.questions[0].topic == "Python"
    assert "req-" not in question_set.questions[0].text
    assert "req-" not in (question_set.questions[0].topic or "")


def test_ai_trace_contains_references_and_hashes_only(db_session: Session) -> None:
    organization, _user, application, job_profile, candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    trace = db_session.get(AITrace, result.ai_trace_id)
    ref = trace.input_reference or {}
    assert ref["entity"] == "job_application"
    assert ref["job_profile_id"] == str(job_profile.id)
    assert ref["candidate_profile_id"] == str(candidate_profile.id)
    assert len(ref["job_profile_sha256"]) == 64
    assert len(ref["candidate_profile_sha256"]) == 64
    output_hash = (trace.output_reference or {})["output_sha256"]
    assert len(output_hash) == 64


def test_provenance_contains_workflow_provider_model_schema(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    question_set = db_session.get(InterviewQuestionSet, result.question_set_id)
    assert question_set.provenance["workflow"] == "interview_question_generation"
    assert question_set.provenance["provider"] == "fake"
    assert question_set.provenance["model"] == "fake-question-model"
    assert question_set.provenance["schema_version"] == "1.2"


def test_uses_fake_provider_without_network_calls(db_session: Session) -> None:
    organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
        db_session
    )
    workflow, _ = make_workflow()

    result = workflow.run(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    db_session.commit()

    trace = db_session.get(AITrace, result.ai_trace_id)
    assert trace.provider == "fake"


# --------------------------------------------------------------------------- #
# SoalProvider (real provider, optional)
# --------------------------------------------------------------------------- #


def _make_soal_workflow() -> tuple[InterviewQuestionGenerationWorkflow, str]:
    api_key = os.environ.get("SOAL_API_KEY")
    if not api_key:
        pytest.skip("SOAL_API_KEY is not set; skipping real Soal provider tests.")
    settings = Settings(
        ai_provider="soal",
        soal_api_key=api_key,
        soal_model="gemini-3.5-flash",
    )
    workflow = InterviewQuestionGenerationWorkflow(provider=get_provider(settings))
    return workflow, api_key


@pytest.mark.soal
class TestSoalProviderInterviewQuestions:
    def test_success_creates_generated_set(self, db_session: Session) -> None:
        organization, _user, application, _job_profile, _candidate_profile = create_parent_records(
            db_session
        )
        workflow, _ = _make_soal_workflow()

        result = workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
        db_session.commit()

        question_set = db_session.get(InterviewQuestionSet, result.question_set_id)
        run = db_session.get(WorkflowRun, result.workflow_run_id)
        step = db_session.get(WorkflowStepTrace, result.workflow_step_trace_id)
        trace = db_session.get(AITrace, result.ai_trace_id)

        assert question_set.status == "generated"
        assert question_set.job_application_id == application.id
        assert question_set.provenance["provider"] == "soal"
        assert len(question_set.questions) >= 1
        assert run.status == "completed"
        assert step.status == "completed"
        assert trace.status == "succeeded"
        assert trace.provider == "soal"

    def test_missing_job_application_fails_before_any_trace(self, db_session: Session) -> None:
        organization, _user, _application, _job_profile, _candidate_profile = create_parent_records(
            db_session
        )
        workflow, _ = _make_soal_workflow()

        with pytest.raises(NotFoundError, match="JobApplication was not found"):
            workflow.run(
                db_session,
                job_application_id=uuid.uuid4(),
                organization_id=organization.id,
            )
        db_session.commit()

        assert count_rows(db_session, WorkflowRun) == 0
        assert count_rows(db_session, AITrace) == 0
        assert count_rows(db_session, InterviewQuestionSet) == 0
