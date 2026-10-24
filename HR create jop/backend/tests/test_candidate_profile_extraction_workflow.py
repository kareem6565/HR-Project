import os
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts import CandidateProfileExtractionOutput
from app.ai.providers.errors import (
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.providers.factory import get_provider
from app.ai.providers.fake import FakeAIProvider
from app.ai.workflows import CandidateProfileExtractionWorkflow
from app.core.config import Settings
from app.models import (
    AITrace,
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    HRDecision,
    MatchEvidence,
    Organization,
    Resume,
    WorkflowRun,
    WorkflowStepTrace,
)
from app.services.errors import ValidationError

RESUME_TEXT = "Ada Lovelace is an engineer skilled in Python."


def create_organization(db_session: Session) -> Organization:
    organization = Organization(name="Candidate Profile Workflow Org")
    db_session.add(organization)
    db_session.flush()
    return organization


def create_candidate(db_session: Session, organization: Organization) -> Candidate:
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Candidate Profile Workflow Candidate",
        email="candidate-profile-workflow@example.com",
    )
    db_session.add(candidate)
    db_session.flush()
    return candidate


def create_resume(db_session: Session, candidate: Candidate) -> Resume:
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/candidate.pdf")
    db_session.add(resume)
    db_session.flush()
    return resume


def valid_payload() -> dict:
    return {
        "full_name": "Ada Lovelace",
        "summary": "Engineer",
        "skills": ["Python"],
        "experience": ["Built analytical engines"],
    }


def make_workflow(
    *,
    payload: dict | None = None,
    failure: ProviderTimeoutError | ProviderRateLimitError | None = None,
) -> tuple[CandidateProfileExtractionWorkflow, FakeAIProvider]:
    provider = FakeAIProvider(
        provider="fake",
        model="fake-model",
        structured_payload=payload if payload is not None else valid_payload(),
        token_usage={"input_tokens": 10, "output_tokens": 5},
        latency_ms=120,
        failure=failure,
    )
    return CandidateProfileExtractionWorkflow(provider), provider


def count_rows(db_session: Session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


def only_one(db_session: Session, model):
    return db_session.scalar(select(model).limit(1))


def test_success_creates_profile_and_traces(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    result = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    profile = db_session.get(CandidateProfile, result.profile_id)
    run = db_session.get(WorkflowRun, result.workflow_run_id)
    step = db_session.get(WorkflowStepTrace, result.workflow_step_trace_id)
    trace = db_session.get(AITrace, result.ai_trace_id)

    assert result.version_number == 1
    assert profile.source == "ai_extracted"
    assert profile.status == "extracted"
    assert profile.is_current is True
    assert profile.profile_data == {
        "schema_version": "1.1",
        **CandidateProfileExtractionOutput.model_validate(
            {"schema_version": "1.1", **valid_payload()}
        ).model_dump(),
    }
    assert run.status == "completed"
    assert step.status == "completed"
    assert step.step_name == "extract_candidate_profile"
    assert trace.status == "succeeded"
    assert trace.provider == "fake"
    assert trace.model_name == "fake-model"
    assert trace.token_usage == {"input_tokens": 10, "output_tokens": 5}


def test_input_reference_contains_resume_identity_and_hash(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    result = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    trace = db_session.get(AITrace, result.ai_trace_id)
    assert trace.input_reference["entity"] == "resume"
    assert trace.input_reference["entity_id"] == str(resume.id)
    assert trace.input_reference["resume_text_sha256"] == _resume_hash()


def _resume_hash() -> str:
    import hashlib

    return hashlib.sha256(RESUME_TEXT.encode("utf-8")).hexdigest()


def test_output_reference_contains_output_hash(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    result = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    trace = db_session.get(AITrace, result.ai_trace_id)
    output_hash = trace.output_reference["output_sha256"]
    assert isinstance(output_hash, str)
    assert len(output_hash) == 64
    int(output_hash, 16)


def test_provenance_contains_workflow_provider_model_schema(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    result = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    profile = db_session.get(CandidateProfile, result.profile_id)
    assert profile.provenance == {
        "workflow": "candidate_profile_extraction",
        "provider": "fake",
        "model": "fake-model",
        "schema_version": "1.1",
    }


def test_reprocessing_creates_new_version_preserves_previous(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    first = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()
    second = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    first_profile = db_session.get(CandidateProfile, first.profile_id)
    second_profile = db_session.get(CandidateProfile, second.profile_id)
    db_session.refresh(first_profile)
    db_session.refresh(second_profile)

    assert first_profile.version_number == 1
    assert second_profile.version_number == 2
    assert first_profile.profile_data == second_profile.profile_data
    assert first_profile.is_current is False
    assert second_profile.is_current is True


def test_multiple_versions_remain_queryable(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()
    workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    versions = list(
        db_session.scalars(
            select(CandidateProfile)
            .where(CandidateProfile.resume_id == resume.id)
            .order_by(CandidateProfile.version_number)
        )
    )
    assert [profile.version_number for profile in versions] == [1, 2]


def test_missing_resume_fails_before_any_trace(db_session: Session) -> None:
    organization = create_organization(db_session)
    create_candidate(db_session, organization)
    workflow, _ = make_workflow()
    db_session.commit()

    with pytest.raises(ValidationError, match="Resume was not found"):
        workflow.run(
            db_session,
            resume_id=uuid.uuid4(),
            organization_id=organization.id,
            resume_text=RESUME_TEXT,
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, AITrace) == 0


def test_organization_mismatch_fails_before_any_trace(db_session: Session) -> None:
    organization_a = create_organization(db_session)
    organization_b = Organization(name="Other Org")
    db_session.add(organization_b)
    db_session.flush()
    candidate_in_b = create_candidate(db_session, organization_b)
    resume_in_b = create_resume(db_session, candidate_in_b)
    workflow, _ = make_workflow()
    db_session.commit()

    with pytest.raises(ValidationError, match="different organization"):
        workflow.run(
            db_session,
            resume_id=resume_in_b.id,
            organization_id=organization_a.id,
            resume_text=RESUME_TEXT,
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, AITrace) == 0


def test_missing_resume_text_fails_before_any_trace(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    with pytest.raises(ValidationError, match="Resume text is required"):
        workflow.run(
            db_session, resume_id=resume.id, organization_id=organization.id, resume_text=""
        )
    db_session.commit()

    assert count_rows(db_session, WorkflowRun) == 0
    assert count_rows(db_session, AITrace) == 0


def test_provider_error_records_failed_and_no_profile(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow(failure=ProviderTimeoutError("timed out"))
    db_session.commit()

    with pytest.raises(ProviderTimeoutError):
        workflow.run(
            db_session,
            resume_id=resume.id,
            organization_id=organization.id,
            resume_text=RESUME_TEXT,
        )
    db_session.commit()

    run = only_one(db_session, WorkflowRun)
    step = only_one(db_session, WorkflowStepTrace)
    trace = only_one(db_session, AITrace)
    assert run.status == "failed"
    assert step.status == "failed"
    assert step.error_type == "ProviderTimeoutError"
    assert trace.status == "failed"
    assert count_rows(db_session, CandidateProfile) == 0


def test_provider_rate_limit_records_failed(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow(failure=ProviderRateLimitError("rate limited"))
    db_session.commit()

    with pytest.raises(ProviderRateLimitError):
        workflow.run(
            db_session,
            resume_id=resume.id,
            organization_id=organization.id,
            resume_text=RESUME_TEXT,
        )
    db_session.commit()

    trace = only_one(db_session, AITrace)
    step = only_one(db_session, WorkflowStepTrace)
    assert trace.status == "failed"
    assert step.status == "failed"
    assert count_rows(db_session, CandidateProfile) == 0


def test_invalid_output_records_validation_failed_and_no_profile(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow(payload={"summary": "missing full_name"})
    db_session.commit()

    with pytest.raises(ValidationError):
        workflow.run(
            db_session,
            resume_id=resume.id,
            organization_id=organization.id,
            resume_text=RESUME_TEXT,
        )
    db_session.commit()

    run = only_one(db_session, WorkflowRun)
    step = only_one(db_session, WorkflowStepTrace)
    trace = only_one(db_session, AITrace)
    assert run.status == "failed"
    assert step.status == "failed"
    assert step.error_type == "ValidationError"
    assert trace.status == "validation_failed"
    assert trace.validation_error is not None
    assert count_rows(db_session, CandidateProfile) == 0


def test_no_hr_decision_candidate_evaluation_or_match_evidence(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    assert count_rows(db_session, HRDecision) == 0
    assert count_rows(db_session, CandidateEvaluation) == 0
    assert count_rows(db_session, MatchEvidence) == 0
    assert count_rows(db_session, CandidateProfile) == 1


def test_uses_fake_provider_without_network_calls(db_session: Session) -> None:
    """The workflow must complete via the in-memory FakeAIProvider only."""
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    result = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    trace = db_session.get(AITrace, result.ai_trace_id)
    assert trace.provider == "fake"
    assert trace.model_name == "fake-model"


def test_no_raw_resume_text_in_ai_trace(db_session: Session) -> None:
    organization = create_organization(db_session)
    candidate = create_candidate(db_session, organization)
    resume = create_resume(db_session, candidate)
    workflow, _ = make_workflow()
    db_session.commit()

    result = workflow.run(
        db_session, resume_id=resume.id, organization_id=organization.id, resume_text=RESUME_TEXT
    )
    db_session.commit()

    trace = db_session.get(AITrace, result.ai_trace_id)
    assert RESUME_TEXT not in str(trace.input_reference or {})
    assert RESUME_TEXT not in str(trace.output_reference or {})
    assert trace.input_reference["resume_text_sha256"] == _resume_hash()
    assert not hasattr(trace, "raw_text")
    assert not hasattr(trace, "raw_prompt")
    assert not hasattr(trace, "full_output")


# --------------------------------------------------------------------------- #
# SoalProvider (real provider, optional)
#
# These tests exercise the workflow against the real Soal adapter selected
# through the provider factory. They only run when a SOAL_API_KEY is present;
# otherwise they skip gracefully so CI and fresh environments stay green. Marked
# ``soal`` so operators can opt-in explicitly with ``pytest -m soal``.
# --------------------------------------------------------------------------- #


def _make_soal_provider() -> tuple[CandidateProfileExtractionWorkflow, str]:
    api_key = os.environ.get("SOAL_API_KEY")
    if not api_key:
        pytest.skip("SOAL_API_KEY is not set; skipping real Soal provider tests.")
    settings = Settings(
        ai_provider="soal",
        soal_api_key=api_key,
        soal_model="gemini-3.5-flash",
    )
    provider = get_provider(settings)
    return CandidateProfileExtractionWorkflow(provider), api_key


@pytest.mark.soal
class TestSoalProviderExtraction:
    def test_success_creates_profile_and_traces(self, db_session: Session) -> None:
        organization = create_organization(db_session)
        candidate = create_candidate(db_session, organization)
        resume = create_resume(db_session, candidate)
        workflow, _ = _make_soal_provider()
        db_session.commit()

        result = workflow.run(
            db_session,
            resume_id=resume.id,
            organization_id=organization.id,
            resume_text=RESUME_TEXT,
        )
        db_session.commit()

        profile = db_session.get(CandidateProfile, result.profile_id)
        trace = db_session.get(AITrace, result.ai_trace_id)
        assert result.version_number == 1
        assert profile.source == "ai_extracted"
        assert profile.status == "extracted"
        assert profile.is_current is True
        assert profile.profile_data["full_name"]
        assert profile.provenance["provider"] == "soal"
        assert profile.provenance["model"] == "gemini-3.5-flash"
        assert trace.status == "succeeded"
        assert trace.provider == "soal"
        assert trace.model_name == "gemini-3.5-flash"
        assert trace.input_reference["entity"] == "resume"
        assert trace.input_reference["entity_id"] == str(resume.id)
        assert trace.input_reference["resume_text_sha256"] == _resume_hash()
        assert set(trace.output_reference) == {"output_sha256"}

    def test_reprocessing_creates_new_version_and_rotates_current(
        self, db_session: Session
    ) -> None:
        organization = create_organization(db_session)
        candidate = create_candidate(db_session, organization)
        resume = create_resume(db_session, candidate)
        workflow, _ = _make_soal_provider()
        db_session.commit()

        first = workflow.run(
            db_session,
            resume_id=resume.id,
            organization_id=organization.id,
            resume_text=RESUME_TEXT,
        )
        db_session.commit()
        second = workflow.run(
            db_session,
            resume_id=resume.id,
            organization_id=organization.id,
            resume_text=RESUME_TEXT,
        )
        db_session.commit()

        first_profile = db_session.get(CandidateProfile, first.profile_id)
        second_profile = db_session.get(CandidateProfile, second.profile_id)
        db_session.refresh(first_profile)
        db_session.refresh(second_profile)

        assert first_profile.version_number == 1
        assert second_profile.version_number == 2
        assert first_profile.is_current is False
        assert second_profile.is_current is True

    def test_missing_resume_fails_before_any_trace(self, db_session: Session) -> None:
        organization = create_organization(db_session)
        create_candidate(db_session, organization)
        workflow, _ = _make_soal_provider()
        db_session.commit()

        with pytest.raises(ValidationError, match="Resume was not found"):
            workflow.run(
                db_session,
                resume_id=uuid.uuid4(),
                organization_id=organization.id,
                resume_text=RESUME_TEXT,
            )
        db_session.commit()

        assert count_rows(db_session, WorkflowRun) == 0
        assert count_rows(db_session, AITrace) == 0

    def test_organization_mismatch_fails_before_any_trace(self, db_session: Session) -> None:
        organization_a = create_organization(db_session)
        organization_b = Organization(name="Other Org")
        db_session.add(organization_b)
        db_session.flush()
        candidate_in_b = create_candidate(db_session, organization_b)
        resume_in_b = create_resume(db_session, candidate_in_b)
        workflow, _ = _make_soal_provider()
        db_session.commit()

        with pytest.raises(ValidationError, match="different organization"):
            workflow.run(
                db_session,
                resume_id=resume_in_b.id,
                organization_id=organization_a.id,
                resume_text=RESUME_TEXT,
            )
        db_session.commit()

        assert count_rows(db_session, WorkflowRun) == 0
        assert count_rows(db_session, AITrace) == 0
