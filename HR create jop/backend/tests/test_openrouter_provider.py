"""Offline HTTP-level coverage for OpenRouter's OpenAI-compatible adapter."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from openai import OpenAI

from app.ai.contracts import CandidateProfileExtractionOutput
from app.ai.providers import (
    OpenRouterProvider,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StructuredGenerationRequest,
    TextGenerationRequest,
)


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


def test_invalid_json_returns_empty_structured_result_without_network_retries(monkeypatch) -> None:
    monkeypatch.setattr("app.ai.providers.openai_compatible.time.sleep", lambda _delay: None)
    provider = _provider(lambda _request: _response("not json"))
    request = StructuredGenerationRequest(
        input="extract", output_schema=CandidateProfileExtractionOutput
    )

    assert provider.generate_structured(request).data is None


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


def test_authentication_error_is_sanitized_into_provider_error() -> None:
    provider = _provider(
        lambda _request: httpx.Response(401, json={"error": {"message": "invalid API key"}})
    )

    with pytest.raises(ProviderInvalidRequestError):
        provider.generate_text(TextGenerationRequest(input="hello"))
