"""HTTP-mocked coverage for self-hosted AI adapters; never calls a real model."""

from __future__ import annotations

import json
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from pydantic import BaseModel

from app.ai.providers.base import StructuredGenerationRequest, TextGenerationRequest
from app.ai.providers.errors import (
    ProviderConfigurationError,
    ProviderContextLimitError,
    ProviderInvalidRequestError,
    ProviderTimeoutError,
    ProviderTruncatedResponseError,
    ProviderUnavailableError,
)
from app.ai.providers.factory import get_provider, resolve_ai_config
from app.ai.providers.local import LocalProvider
from app.ai.providers.ollama_local import OllamaLocalProvider
from app.core.config import Settings


class _Answer(BaseModel):
    answer: str


def _ollama_response(
    *,
    content: str = "hello",
    prompt_count: int = 9,
    output_count: int = 2,
    done: bool = True,
    done_reason: str = "stop",
) -> dict:
    return {
        "model": "chosen-model",
        "message": {"role": "assistant", "content": content},
        "done": done,
        "done_reason": done_reason,
        "prompt_eval_count": prompt_count,
        "eval_count": output_count,
    }


def _ollama(
    handler: Callable[[httpx.Request], httpx.Response], *, num_ctx: int = 16
) -> OllamaLocalProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaLocalProvider(
        model="chosen-model",
        base_url="http://ollama.test:11434",
        num_ctx=num_ctx,
        http_client=client,
    )


def _metering(monkeypatch: pytest.MonkeyPatch):
    event_id = uuid4()
    recorded: list[tuple] = []
    monkeypatch.setattr(
        "app.ai.cost_policy.authorize_self_hosted_and_reserve",
        lambda **_kwargs: event_id,
    )
    monkeypatch.setattr(
        "app.ai.cost_policy.record_result",
        lambda *args, **kwargs: recorded.append((args, kwargs)),
    )
    return event_id, recorded


def test_native_ollama_structured_request_uses_documented_schema_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []
    event_id, records = _metering(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_ollama_response(content='{"answer":"ready"}'))

    result = _ollama(handler).generate_structured(
        StructuredGenerationRequest(
            input="Return a short status.",
            system_prompt="Follow the provided schema.",
            output_schema=_Answer,
        )
    )

    assert result.data == {"answer": "ready"}
    assert result.token_usage == {"prompt_tokens": 9, "completion_tokens": 2}
    assert captured[0]["options"] == {"num_ctx": 16}
    assert captured[0]["format"] == _Answer.model_json_schema()
    assert captured[0]["stream"] is False
    assert captured[0]["messages"][0] == {
        "role": "system",
        "content": "Follow the provided schema.",
    }
    assert records[0][0] == (event_id,)
    assert records[0][1]["status"] == "succeeded"
    assert records[0][1]["response"]["usage"] == {
        "prompt_tokens": 9,
        "completion_tokens": 2,
    }


def test_native_ollama_context_boundary_is_typed_metered_and_discarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id, records = _metering(monkeypatch)
    provider = _ollama(lambda _request: httpx.Response(200, json=_ollama_response(prompt_count=16)))

    with pytest.raises(ProviderContextLimitError):
        provider.generate_text(TextGenerationRequest(input="A synthetic prompt"))

    assert records[0][0] == (event_id,)
    assert records[0][1]["status"] == "failed"
    assert records[0][1]["error"].__class__ is ProviderContextLimitError


def test_native_ollama_incomplete_generation_is_typed_metered_and_discarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, records = _metering(monkeypatch)
    provider = _ollama(
        lambda _request: httpx.Response(
            200, json=_ollama_response(done=False, done_reason="length")
        )
    )

    with pytest.raises(ProviderTruncatedResponseError):
        provider.generate_text(TextGenerationRequest(input="A synthetic prompt"))

    assert records[0][1]["status"] == "failed"


def test_native_ollama_bad_structured_json_is_failed_in_usage_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, records = _metering(monkeypatch)
    provider = _ollama(
        lambda _request: httpx.Response(200, json=_ollama_response(content="not valid json"))
    )

    with pytest.raises(ProviderInvalidRequestError):
        provider.generate_structured(
            StructuredGenerationRequest(input="Synthetic only", output_schema=_Answer)
        )

    assert records[0][1]["status"] == "failed"


def test_native_ollama_connection_error_maps_to_visible_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, records = _metering(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mock connection failure", request=request)

    with pytest.raises(ProviderUnavailableError):
        _ollama(handler).generate_text(TextGenerationRequest(input="A synthetic prompt"))
    assert records[0][1]["status"] == "failed"


def test_native_ollama_timeout_maps_to_visible_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, records = _metering(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("mock timeout", request=request)

    with pytest.raises(ProviderTimeoutError):
        _ollama(handler).generate_text(TextGenerationRequest(input="A synthetic prompt"))
    assert records[0][1]["status"] == "failed"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not json", headers={"content-type": "application/json"}),
        httpx.Response(200, json={"message": {}, "done": True}),
    ],
)
def test_native_ollama_malformed_responses_are_typed_and_metered(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> None:
    _, records = _metering(monkeypatch)

    with pytest.raises(ProviderInvalidRequestError):
        _ollama(lambda _request: response).generate_text(
            TextGenerationRequest(input="A synthetic prompt")
        )
    assert records[0][1]["status"] == "failed"


def test_generic_local_provider_keeps_openai_compatible_json_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []
    event_id = uuid4()
    policy_calls: list[tuple] = []
    monkeypatch.setattr(
        "app.ai.cost_policy.authorize_self_hosted_and_reserve",
        lambda **kwargs: policy_calls.append(("reserve", kwargs)) or event_id,
    )
    monkeypatch.setattr(
        "app.ai.cost_policy.record_result",
        lambda *args, **kwargs: policy_calls.append(("record", args, kwargs)),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "mock-local",
                "choices": [{"message": {"role": "assistant", "content": '{"answer":"ready"}'}}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 2},
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = LocalProvider(
        model="chosen-model",
        base_url="http://vllm.test:8000/v1",
        http_client=http_client,
    )
    result = provider.generate_structured(
        StructuredGenerationRequest(input="Synthetic only", output_schema=_Answer)
    )

    assert result.provider == "local"
    assert result.data == {"answer": "ready"}
    assert captured[0]["model"] == "chosen-model"
    assert captured[0]["response_format"] == {"type": "json_object"}
    assert policy_calls[0][0] == "reserve"
    assert policy_calls[0][1]["provider"] == "local"
    assert policy_calls[1][0] == "record"
    assert policy_calls[1][1] == (event_id,)


def test_factory_keeps_cloud_and_self_hosted_ollama_provider_ids_distinct() -> None:
    cloud = Settings(ai_provider="ollama", ollama_api_key="test-key")
    native = Settings(
        ai_provider="ollama_local",
        ollama_local_model="operator-selected-model",
        ollama_local_num_ctx=24576,
    )
    generic = Settings(
        ai_provider="local",
        local_llm_model="operator-selected-openai-compatible-model",
    )

    assert resolve_ai_config(cloud)["provider"] == "ollama"
    assert resolve_ai_config(native)["provider"] == "ollama_local"
    assert resolve_ai_config(generic)["provider"] == "local"
    assert isinstance(get_provider(native), OllamaLocalProvider)
    assert get_provider(native).num_ctx == 24576
    assert isinstance(get_provider(generic), LocalProvider)

    with pytest.raises(ProviderConfigurationError):
        get_provider(Settings(ai_provider="ollama_local"))
