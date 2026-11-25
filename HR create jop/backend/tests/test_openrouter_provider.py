"""Offline HTTP-level coverage for OpenRouter's OpenAI-compatible adapter."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from openai import OpenAI
from pydantic import BaseModel

from app.ai.contracts import CandidateProfileExtractionOutput
from app.ai.providers import (
    OpenRouterProvider,
    ProviderConfigurationError,
    ProviderInsufficientCreditsError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StructuredGenerationRequest,
    TextGenerationRequest,
)


class _Answer(BaseModel):
    answer: str


def _response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "mock-completion",
            "object": "chat.completion",
            "created": 1,
            "model": "deepseek/deepseek-v4.1-flash-1017",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        },
    )


def _provider(handler: Callable[[httpx.Request], httpx.Response]) -> OpenRouterProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    sdk_client = OpenAI(
        api_key="offline-test-key",
        base_url="https://openrouter.invalid/api/v1",
        max_retries=0,
        http_client=client,
    )
    provider = OpenRouterProvider(api_key="offline-test-key", max_retries=0)
    provider.cost_policy_enabled = False  # This suite tests the transport adapter in isolation.
    provider._client = sdk_client
    return provider


def test_text_generation_uses_openrouter_chat_completions_offline() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _response("Hello from a mocked endpoint")

    result = _provider(handler).generate_text(TextGenerationRequest(input="Say hello"))

    assert result.provider == "openrouter"
    assert result.text == "Hello from a mocked endpoint"
    assert result.token_usage == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    assert captured[0].url.path.endswith("/chat/completions")
    assert captured[0].headers["authorization"] == "Bearer offline-test-key"


def test_structured_json_response_is_parsed_and_keeps_contract_version() -> None:
    payload = {
        "full_name": "Ada Lovelace",
        "summary": "Mathematician",
        "skills": ["Python"],
        "experience": [],
    }
    provider = _provider(lambda _request: _response(json.dumps(payload)))
    request = StructuredGenerationRequest(
        input="extract", output_schema=CandidateProfileExtractionOutput
    )

    result = provider.generate_structured(request)

    assert result.data == payload
    assert CandidateProfileExtractionOutput.model_validate(result.data).full_name == "Ada Lovelace"
    assert result.schema_version == request.schema_version


def test_free_router_constraint_is_sent_in_supported_request_body(monkeypatch) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _response('{"answer":"ok"}')

    monkeypatch.setattr(
        "app.ai.cost_policy.authorize_and_reserve", lambda **_kwargs: "offline-event"
    )
    monkeypatch.setattr("app.ai.cost_policy.record_result", lambda *_args, **_kwargs: None)
    provider = _provider(handler)
    provider.model_name = "openrouter/free"
    provider.cost_policy_enabled = True

    result = provider.generate_structured(
        StructuredGenerationRequest(input="synthetic only", output_schema=_Answer)
    )

    assert result.data == {"answer": "ok"}
    body = json.loads(captured[0].content)
    assert body["provider"] == {"require_parameters": True}


def test_invalid_json_is_a_traced_failure_without_paid_retries(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response("not json")

    provider = _provider(handler)
    request = StructuredGenerationRequest(
        input="extract", output_schema=CandidateProfileExtractionOutput
    )

    with pytest.raises(ProviderInvalidResponseError) as raised:
        provider.generate_structured(request)

    assert raised.value.error_code == "invalid_structured_response"
    assert len(requests) == 1


def test_unsupported_response_format_retries_without_parameter(monkeypatch) -> None:
    monkeypatch.setattr("app.ai.providers.openai_compatible.time.sleep", lambda _delay: None)
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if "response_format" in body:
            return httpx.Response(
                400, json={"error": {"message": "response_format json_object is unsupported"}}
            )
        return _response(
            json.dumps({"full_name": "Ada", "summary": "s", "skills": [], "experience": []})
        )

    result = _provider(handler).generate_structured(
        StructuredGenerationRequest(input="extract", output_schema=CandidateProfileExtractionOutput)
    )

    assert result.data["full_name"] == "Ada"
    assert "response_format" in requests[0]
    assert "response_format" not in requests[1]


def test_rate_limit_is_classified_without_real_retries(monkeypatch) -> None:
    monkeypatch.setattr("app.ai.providers.openai_compatible.time.sleep", lambda _delay: None)
    provider = _provider(
        lambda _request: httpx.Response(429, json={"error": {"message": "rate limited"}})
    )

    with pytest.raises(ProviderRateLimitError):
        provider.generate_text(TextGenerationRequest(input="hello"))


def test_timeout_is_classified() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("mock timeout")

    with pytest.raises(ProviderTimeoutError):
        _provider(handler).generate_text(TextGenerationRequest(input="hello"))


def test_authentication_error_is_classified_as_bad_key() -> None:
    provider = _provider(
        lambda _request: httpx.Response(401, json={"error": {"message": "invalid API key"}})
    )

    with pytest.raises(ProviderConfigurationError) as raised:
        provider.generate_text(TextGenerationRequest(input="hello"))
    assert raised.value.error_code == "invalid_api_key"


def test_provider_credit_error_is_classified_separately() -> None:
    provider = _provider(
        lambda _request: httpx.Response(402, json={"error": {"message": "insufficient credits"}})
    )

    with pytest.raises(ProviderInsufficientCreditsError):
        provider.generate_text(TextGenerationRequest(input="hello"))
