"""Focused unit tests for the Phase 3.3 AI provider abstraction."""

from copy import deepcopy

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts import (
    AI_CONTRACT_SCHEMA_VERSION,
    CandidateProfileExtractionOutput,
    JobProfileExtractionOutput,
    validate_candidate_profile_extraction,
    validate_job_profile_extraction,
)
from app.ai.providers import (
    FakeAIProvider,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StructuredGenerationRequest,
    TextGenerationRequest,
    provider_error_for,
)
from app.ai.providers.base import AIProvider
from app.ai.results import StructuredAIResult, TextAIResult
from app.models import (
    AITrace,
    CandidateEvaluation,
    HRDecision,
    MatchEvidence,
    WorkflowRun,
    WorkflowStepTrace,
)


def _job_payload() -> dict:
    return {"title": "Backend Engineer", "requirements": ["Python", "PostgreSQL"]}


def _candidate_payload() -> dict:
    return {"full_name": "Ada Lovelace", "skills": ["Python", "SQL"]}


def _count_rows(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --------------------------------------------------------------------------- #
# Interface / result types
# --------------------------------------------------------------------------- #


def test_interface_is_abstract() -> None:
    assert hasattr(AIProvider, "generate_structured")
    assert hasattr(AIProvider, "generate_text")
    with pytest.raises(TypeError):
        AIProvider()  # abstract interface cannot be instantiated


def test_structured_generation_returns_structured_result() -> None:
    provider = FakeAIProvider(structured_payload=_job_payload())
    result = provider.generate_structured(StructuredGenerationRequest(input="extract job profile"))
    assert isinstance(result, StructuredAIResult)


def test_text_generation_returns_text_result() -> None:
    provider = FakeAIProvider(text="hello")
    result = provider.generate_text(TextGenerationRequest(input="say hi"))
    assert isinstance(result, TextAIResult)


# --------------------------------------------------------------------------- #
# Deterministic generation
# --------------------------------------------------------------------------- #


def test_structured_generation_is_deterministic() -> None:
    provider = FakeAIProvider(structured_payload=_job_payload())
    request = StructuredGenerationRequest(input="extract job profile")
    first = provider.generate_structured(request)
    second = provider.generate_structured(request)
    assert first.data == second.data == _job_payload()
    assert first == second


def test_text_generation_is_deterministic() -> None:
    provider = FakeAIProvider(text="fixed response")
    request = TextGenerationRequest(input="say hi")
    assert provider.generate_text(request).text == "fixed response"
    assert provider.generate_text(request).text == "fixed response"


# --------------------------------------------------------------------------- #
# Configured metadata, token usage, latency
# --------------------------------------------------------------------------- #


def test_configured_provider_model_token_usage_latency_structured() -> None:
    token_usage = {"input": 5, "output": 10, "total": 15}
    provider = FakeAIProvider(
        provider="fake-vendor",
        model="fake-1",
        structured_payload=_job_payload(),
        token_usage=token_usage,
        latency_ms=42,
    )
    result = provider.generate_structured(StructuredGenerationRequest(input="x"))
    assert result.provider == "fake-vendor"
    assert result.model == "fake-1"
    assert result.token_usage == token_usage
    assert result.latency_ms == 42


def test_configured_provider_model_token_usage_latency_text() -> None:
    token_usage = {"input": 3, "output": 4}
    provider = FakeAIProvider(
        provider="fake-vendor",
        model="fake-1",
        text="hello",
        token_usage=token_usage,
        latency_ms=12,
    )
    result = provider.generate_text(TextGenerationRequest(input="x"))
    assert result.provider == "fake-vendor"
    assert result.model == "fake-1"
    assert result.token_usage == token_usage
    assert result.latency_ms == 12


def test_structured_result_echoes_request_schema_version() -> None:
    provider = FakeAIProvider(structured_payload=_job_payload())
    request = StructuredGenerationRequest(input="x", schema_version="1.0")
    result = provider.generate_structured(request)
    assert result.schema_version == "1.0"


def test_metadata_is_nullable_when_not_configured() -> None:
    provider = FakeAIProvider(structured_payload={})
    result = provider.generate_structured(StructuredGenerationRequest(input="x"))
    assert result.model is None
    assert result.token_usage is None
    assert result.latency_ms is None
    assert result.schema_version == AI_CONTRACT_SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# Deep-copy / isolation
# --------------------------------------------------------------------------- #


def test_structured_payload_is_deep_copied() -> None:
    original = {"nested": {"skills": ["Python"]}}
    provider = FakeAIProvider(structured_payload=original)
    result = provider.generate_structured(StructuredGenerationRequest(input="x"))
    result.data["nested"]["skills"].append("SQL")
    assert original["nested"]["skills"] == ["Python"]


def test_repeated_calls_do_not_mutate_configured_payload() -> None:
    provider = FakeAIProvider(structured_payload=_job_payload())
    request = StructuredGenerationRequest(input="x")
    first = provider.generate_structured(request)
    first.data["requirements"].append("Docker")
    second = provider.generate_structured(request)
    assert second.data == _job_payload()


# --------------------------------------------------------------------------- #
# Provider failure kinds / error classification
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("timeout", ProviderTimeoutError),
        ("rate_limit", ProviderRateLimitError),
        ("unavailable", ProviderUnavailableError),
        ("invalid_request", ProviderInvalidRequestError),
    ],
)
def test_failure_kind_raises_mapped_error(kind, expected) -> None:
    assert provider_error_for(kind) is expected
    provider = FakeAIProvider(structured_payload={}, failure_kind=kind)
    with pytest.raises(expected):
        provider.generate_structured(StructuredGenerationRequest(input="x"))


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("timeout", ProviderTimeoutError),
        ("rate_limit", ProviderRateLimitError),
        ("unavailable", ProviderUnavailableError),
        ("invalid_request", ProviderInvalidRequestError),
    ],
)
def test_failure_kind_raises_error_for_text(kind, expected) -> None:
    provider = FakeAIProvider(text="x", failure_kind=kind)
    with pytest.raises(expected):
        provider.generate_text(TextGenerationRequest(input="x"))


def test_exact_provider_exception_is_raised() -> None:
    error = ProviderTimeoutError("custom message")
    provider = FakeAIProvider(structured_payload={}, failure=error)
    with pytest.raises(ProviderTimeoutError) as excinfo:
        provider.generate_structured(StructuredGenerationRequest(input="x"))
    assert excinfo.value is error


def test_failure_and_failure_kind_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        FakeAIProvider(
            structured_payload={},
            failure=ProviderTimeoutError("x"),
            failure_kind="timeout",
        )


def test_unknown_failure_kind_rejected() -> None:
    with pytest.raises(ValueError):
        provider_error_for("unknown")


def test_clear_failure_restores_success() -> None:
    provider = FakeAIProvider(
        structured_payload=_job_payload(),
        failure_kind="unavailable",
    )
    with pytest.raises(ProviderUnavailableError):
        provider.generate_structured(StructuredGenerationRequest(input="x"))
    provider.clear_failure()
    result = provider.generate_structured(StructuredGenerationRequest(input="x"))
    assert result.data == _job_payload()


# --------------------------------------------------------------------------- #
# No database / no persistence
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "model",
    [
        WorkflowRun,
        WorkflowStepTrace,
        AITrace,
        HRDecision,
        CandidateEvaluation,
        MatchEvidence,
    ],
)
def test_provider_does_not_persist_any_domain_entity(db_session, model) -> None:
    provider = FakeAIProvider(structured_payload=_job_payload(), text="hello")
    provider.generate_structured(StructuredGenerationRequest(input="x"))
    provider.generate_text(TextGenerationRequest(input="x"))
    db_session.flush()
    assert _count_rows(db_session, model) == 0


def test_provider_does_not_perform_scoring(db_session) -> None:
    provider = FakeAIProvider(structured_payload=_job_payload())
    provider.generate_structured(StructuredGenerationRequest(input="x"))
    db_session.flush()
    assert _count_rows(db_session, CandidateEvaluation) == 0


# --------------------------------------------------------------------------- #
# Contract boundary (generic structured result -> Phase 3.2 validation)
# --------------------------------------------------------------------------- #


def test_structured_result_crosses_job_profile_validation_boundary() -> None:
    provider = FakeAIProvider(structured_payload=_job_payload())
    result = provider.generate_structured(
        StructuredGenerationRequest(
            input="extract job profile",
            output_schema=JobProfileExtractionOutput,
        )
    )
    contract = validate_job_profile_extraction(result.data)
    assert isinstance(contract, JobProfileExtractionOutput)
    assert contract.title == "Backend Engineer"


def test_structured_result_crosses_candidate_profile_validation_boundary() -> None:
    provider = FakeAIProvider(structured_payload=_candidate_payload())
    result = provider.generate_structured(
        StructuredGenerationRequest(
            input="extract candidate profile",
            output_schema=CandidateProfileExtractionOutput,
        )
    )
    contract = validate_candidate_profile_extraction(result.data)
    assert isinstance(contract, CandidateProfileExtractionOutput)
    assert contract.full_name == "Ada Lovelace"
    assert contract.skills == ["Python", "SQL"]


def test_result_data_deepcopy_is_independent_from_contract_validation_use() -> None:
    provider = FakeAIProvider(structured_payload=_job_payload())
    result = provider.generate_structured(StructuredGenerationRequest(input="x"))
    original = deepcopy(result.data)
    contract = validate_job_profile_extraction(result.data)
    assert contract.title == original["title"]
