"""Hermetic unit tests for the Soal provider adapter and provider factory.

These tests never make network calls: the OpenAI client is replaced with fakes,
and ``db_session`` fixtures are only used to assert that provider calls never
write trace/run rows.
"""

from __future__ import annotations

from unittest import mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts import CandidateProfileExtractionOutput, JobProfileExtractionOutput
from app.ai.providers import (
    FakeAIProvider,
    OllamaCloudProvider,
    ProviderConfigurationError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SoalProvider,
    StructuredGenerationRequest,
    TextGenerationRequest,
    get_provider,
)
from app.ai.results import StructuredAIResult, TextAIResult
from app.core.config import Settings
from app.models import AITrace, WorkflowRun, WorkflowStepTrace


class _FakeUsage:
    """Minimal stand-in for an OpenAI ``usage`` object."""

    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _FakeMessage:
    """Minimal stand-in for an OpenAI ``message`` object."""

    def __init__(self, content) -> None:
        self.content = content


class _FakeChoice:
    """Minimal stand-in for an OpenAI ``choice`` object."""

    def __init__(self, message) -> None:
        self.message = message


class _FakeCompletion:
    """Minimal stand-in for an OpenAI ``chat.completions.create`` response."""

    def __init__(self, message, usage=None) -> None:
        self.choices = [_FakeChoice(message)]
        self.usage = usage


class _FakeCompletions:
    """Stand-in for ``client.chat.completions``."""

    def __init__(self, completion=None, exception=None, sequence=None) -> None:
        self._completion = completion
        self._exception = exception
        self._sequence = sequence
        self._call_count = 0

    def create(self, **_kwargs):
        if self._exception is not None:
            raise self._exception
        if self._sequence is not None:
            item = self._sequence[min(self._call_count, len(self._sequence) - 1)]
            self._call_count += 1
            return item
        return self._completion


class _FakeChat:
    def __init__(self, completions) -> None:
        self.completions = completions


class _FakeOpenAI:
    """Stand-in for ``openai.OpenAI`` (accepts the real constructor kwargs)."""

    def __init__(self, completions, **_kwargs) -> None:
        self.chat = _FakeChat(completions)


class _HTTPError(Exception):
    """Stand-in vendor error carrying an HTTP status code."""

    def __init__(self, status_code: int, message: str = "provider error") -> None:
        super().__init__(message)
        self.status_code = status_code


def _patch_client(completions: _FakeCompletions) -> mock._patch:
    return mock.patch(
        "app.ai.providers.soal.OpenAI",
        return_value=_FakeOpenAI(completions),
    )


def _completion(content, usage=None) -> _FakeCompletion:
    return _FakeCompletion(_FakeMessage(content), usage=usage)


def _structured_request(schema) -> StructuredGenerationRequest:
    return StructuredGenerationRequest(input="extract candidate profile", output_schema=schema)


def _candidate_payload() -> dict:
    return {
        "full_name": "Ada Lovelace",
        "summary": "Mathematician",
        "skills": ["Python"],
        "experience": [],
    }


def json_payload_dict() -> dict:
    return _candidate_payload()


def json_payload() -> str:
    return (
        '{"full_name": "Ada Lovelace", "summary": "Mathematician", '
        '"skills": ["Python"], "experience": []}'
    )


def _structured_provider(completions: _FakeCompletions) -> SoalProvider:
    with _patch_client(completions):
        return SoalProvider(api_key="test-key", model="gemini-3.5-flash")


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --------------------------------------------------------------------------- #
# Structured generation
# --------------------------------------------------------------------------- #


def test_structured_result_exposes_provider_and_model_with_valid_data() -> None:
    provider = _structured_provider(_FakeCompletions(completion=_completion(json_payload())))

    result = provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))

    assert isinstance(result, StructuredAIResult)
    assert result.provider == "soal"
    assert result.model == "gemini-3.5-flash"
    assert result.data == _candidate_payload()


def test_structured_data_matches_output_schema_when_content_is_dict() -> None:
    payload = {
        "full_name": "Alan Turing",
        "summary": "Enigma breaker",
        "skills": ["Logic"],
        "experience": [],
    }
    provider = _structured_provider(_FakeCompletions(completion=_completion(payload)))

    result = provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))

    assert result.data == payload


def test_structured_with_job_profile_schema() -> None:
    payload = {
        "title": "Backend Engineer",
        "summary": "Builds services",
        "requirements": [{"text": "Python", "category": "must_have", "dimension": "skill"}],
    }
    provider = _structured_provider(_FakeCompletions(completion=_completion(payload)))

    result = provider.generate_structured(_structured_request(JobProfileExtractionOutput))

    assert result.data == payload
    assert result.schema_version == "1.1"


def test_structured_extracts_token_usage_from_usage() -> None:
    usage = _FakeUsage(prompt_tokens=12, completion_tokens=8, total_tokens=20)
    provider = _structured_provider(
        _FakeCompletions(
            completion=_completion(
                content={"full_name": "Ada", "summary": "s", "skills": [], "experience": []},
                usage=usage,
            )
        )
    )

    result = provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))

    assert result.token_usage == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }


def test_structured_records_positive_latency() -> None:
    provider = _structured_provider(
        _FakeCompletions(
            completion=_completion(
                content={"full_name": "Ada", "summary": "s", "skills": [], "experience": []}
            )
        )
    )

    result = provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))

    assert result.latency_ms is not None
    assert result.latency_ms >= 0


def test_structured_without_schema_returns_no_data() -> None:
    provider = _structured_provider(_FakeCompletions(completion=_completion("not structured")))

    result = provider.generate_structured(StructuredGenerationRequest(input="plain"))

    assert result.data is None


def test_structured_retries_when_parsing_fails_then_succeeds() -> None:
    bad = _completion("not valid json at all")
    good = _completion(json_payload())
    provider = _structured_provider(_FakeCompletions(sequence=[bad, good]))

    result = provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))

    assert result.data == json_payload_dict()


def test_structured_exhausts_retries_and_returns_none() -> None:
    provider = _structured_provider(_FakeCompletions(completion=_completion("always broken")))

    result = provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))

    assert result.data is None


# --------------------------------------------------------------------------- #
# Text generation
# --------------------------------------------------------------------------- #


def test_text_result_exposes_provider_model_text_and_usage() -> None:
    usage = _FakeUsage(prompt_tokens=4, completion_tokens=6, total_tokens=10)
    provider = _structured_provider(
        _FakeCompletions(completion=_completion("short cover letter", usage=usage))
    )

    result = provider.generate_text(TextGenerationRequest(input="write a summary"))

    assert isinstance(result, TextAIResult)
    assert result.provider == "soal"
    assert result.model == "gemini-3.5-flash"
    assert result.text == "short cover letter"
    assert result.token_usage == {
        "prompt_tokens": 4,
        "completion_tokens": 6,
        "total_tokens": 10,
    }


# --------------------------------------------------------------------------- #
# Error mapping
# --------------------------------------------------------------------------- #


def test_timeout_error_is_mapped() -> None:
    provider = _structured_provider(_FakeCompletions(exception=TimeoutError("request timed out")))

    with pytest.raises(ProviderTimeoutError):
        provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))


def test_http_timeout_status_is_mapped() -> None:
    provider = _structured_provider(_FakeCompletions(exception=_HTTPError(504, "gateway timeout")))

    with pytest.raises(ProviderTimeoutError):
        provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))


def test_rate_limit_error_is_mapped() -> None:
    provider = _structured_provider(
        _FakeCompletions(exception=_HTTPError(429, "resource exhausted"))
    )

    with pytest.raises(ProviderRateLimitError):
        provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))


def test_invalid_request_error_is_mapped() -> None:
    provider = _structured_provider(_FakeCompletions(exception=_HTTPError(400, "invalid argument")))

    with pytest.raises(ProviderInvalidRequestError):
        provider.generate_text(TextGenerationRequest(input="boom"))


def test_server_error_is_mapped_to_unavailable() -> None:
    provider = _structured_provider(_FakeCompletions(exception=_HTTPError(500, "internal error")))

    with pytest.raises(ProviderUnavailableError):
        provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))


def test_unknown_error_is_mapped_to_unavailable() -> None:
    provider = _structured_provider(_FakeCompletions(exception=RuntimeError("mystery failure")))

    with pytest.raises(ProviderUnavailableError):
        provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))


# --------------------------------------------------------------------------- #
# Persistence boundaries
# --------------------------------------------------------------------------- #


def test_structured_generation_writes_no_db_rows(db_session: Session) -> None:
    provider = _structured_provider(
        _FakeCompletions(
            completion=_completion(
                content={"full_name": "Ada", "summary": "s", "skills": [], "experience": []}
            )
        )
    )

    provider.generate_structured(_structured_request(CandidateProfileExtractionOutput))

    assert _count(db_session, WorkflowRun) == 0
    assert _count(db_session, WorkflowStepTrace) == 0
    assert _count(db_session, AITrace) == 0


def test_text_generation_writes_no_db_rows(db_session: Session) -> None:
    provider = _structured_provider(_FakeCompletions(completion=_completion("hello")))

    provider.generate_text(TextGenerationRequest(input="hi"))

    assert _count(db_session, WorkflowRun) == 0
    assert _count(db_session, WorkflowStepTrace) == 0
    assert _count(db_session, AITrace) == 0


# --------------------------------------------------------------------------- #
# Provider factory
# --------------------------------------------------------------------------- #


def test_factory_returns_soal_with_key() -> None:
    settings = Settings(ai_provider="soal", soal_api_key="secret", soal_model="gemini-3.5-flash")
    with mock.patch(
        "app.ai.providers.soal.OpenAI",
        return_value=_FakeOpenAI(_FakeCompletions()),
    ):
        provider = get_provider(settings)

    assert isinstance(provider, SoalProvider)
    assert provider.model_name == "gemini-3.5-flash"
    assert provider.base_url == "https://soal.help/api/v1"


def test_factory_returns_ollama_cloud_with_key() -> None:
    settings = Settings(ai_provider="ollama", ollama_api_key="secret")
    with mock.patch(
        "app.ai.providers.soal.OpenAI",
        return_value=_FakeOpenAI(_FakeCompletions()),
    ):
        provider = get_provider(settings)

    assert isinstance(provider, OllamaCloudProvider)
    assert provider.provider_name == "ollama"
    assert provider.model_name == "gemma4:31b"
    assert provider.base_url == "https://ollama.com/v1"


def test_factory_requires_ollama_key_instead_of_using_fake() -> None:
    settings = Settings(ai_provider="ollama", ollama_api_key=None)

    with pytest.raises(ProviderConfigurationError, match="OLLAMA_API_KEY"):
        get_provider(settings)


def test_factory_returns_fake_in_fake_mode() -> None:
    settings = Settings(ai_provider="fake", soal_api_key="secret")

    provider = get_provider(settings, provider="fake", model="fake-model")

    assert isinstance(provider, FakeAIProvider)


def test_factory_falls_back_to_fake_when_key_missing() -> None:
    settings = Settings(ai_provider="soal", soal_api_key=None)

    provider = get_provider(settings)

    assert isinstance(provider, FakeAIProvider)


def test_factory_forwards_kwargs_only_to_fake() -> None:
    settings = Settings(ai_provider="fake")
    payload = {"full_name": "Ada", "summary": "s", "skills": [], "experience": []}

    provider = get_provider(settings, structured_payload=payload)

    assert isinstance(provider, FakeAIProvider)
    result = provider.generate_structured(
        StructuredGenerationRequest(input="x", output_schema=CandidateProfileExtractionOutput)
    )
    assert result.data == payload
