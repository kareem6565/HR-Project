"""Native Ollama `/api/chat` adapter for self-hosted installations."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.ai.providers.base import AIProvider, StructuredGenerationRequest, TextGenerationRequest
from app.ai.providers.errors import (
    ProviderContextLimitError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderTruncatedResponseError,
    ProviderUnavailableError,
)
from app.ai.results import StructuredAIResult, TextAIResult


class OllamaLocalProvider(AIProvider):
    """Use Ollama's documented native chat API to set per-request context size."""

    provider_name = "ollama_local"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        num_ctx: int = 16384,
        timeout: float = 180.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout)
        self.cost_policy_enabled = True

    def generate_structured(self, request: StructuredGenerationRequest) -> StructuredAIResult:
        started = time.monotonic()
        schema = request.output_schema.model_json_schema() if request.output_schema else None
        payload = self._generate(
            input_text=request.input,
            system_prompt=request.system_prompt,
            schema=schema,
            require_json=request.output_schema is not None,
            metadata=request.metadata,
        )
        content = payload["message"]["content"]
        data = _parse_json_object(content)
        if request.output_schema is not None and data is None:
            raise ProviderInvalidRequestError("Ollama returned invalid structured JSON.")
        return StructuredAIResult(
            provider=self.provider_name,
            model=self.model_name,
            token_usage=_usage(payload),
            latency_ms=int((time.monotonic() - started) * 1000),
            data=data,
            schema_version=request.schema_version,
        )

    def generate_text(self, request: TextGenerationRequest) -> TextAIResult:
        started = time.monotonic()
        payload = self._generate(input_text=request.input, metadata=request.metadata)
        return TextAIResult(
            provider=self.provider_name,
            model=self.model_name,
            token_usage=_usage(payload),
            latency_ms=int((time.monotonic() - started) * 1000),
            text=payload["message"]["content"],
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _generate(
        self,
        *,
        input_text: str,
        metadata: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        schema: dict[str, Any] | None = None,
        require_json: bool = False,
    ) -> dict[str, Any]:
        from app.ai.cost_policy import authorize_self_hosted_and_reserve, record_result

        event_id = None
        response_payload: dict[str, Any] | None = None
        try:
            if self.cost_policy_enabled:
                event_id = authorize_self_hosted_and_reserve(
                    provider=self.provider_name, model=self.model_name, metadata=metadata
                )
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": input_text})
            body: dict[str, Any] = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {"num_ctx": self.num_ctx},
            }
            if schema is not None:
                body["format"] = schema
            response = self._client.post(f"{self.base_url}/api/chat", json=body)
            if response.status_code == 429:
                raise ProviderRateLimitError("Ollama local server is rate-limiting requests.")
            if response.status_code in (408, 504):
                raise ProviderTimeoutError("Ollama local request timed out.")
            if response.status_code >= 400:
                raise ProviderUnavailableError(
                    f"Ollama local server returned HTTP {response.status_code}."
                )
            try:
                response_payload = response.json()
            except (ValueError, json.JSONDecodeError) as error:
                raise ProviderInvalidRequestError(
                    "Ollama local server returned invalid JSON."
                ) from error
            self._verify_complete(response_payload)
            if require_json and _parse_json_object(response_payload["message"]["content"]) is None:
                raise ProviderInvalidRequestError(
                    "Ollama local server returned invalid structured JSON."
                )
        except (ProviderContextLimitError, ProviderTruncatedResponseError) as error:
            if event_id is not None:
                record_result(
                    event_id,
                    status="failed",
                    response=_ledger_response(response_payload),
                    error=error,
                )
            raise
        except (
            ProviderRateLimitError,
            ProviderTimeoutError,
            ProviderInvalidRequestError,
            ProviderUnavailableError,
        ) as error:
            if event_id is not None:
                record_result(
                    event_id,
                    status="failed",
                    response=_ledger_response(response_payload),
                    error=error,
                )
            raise
        except httpx.TimeoutException as error:
            mapped = ProviderTimeoutError("Ollama local request timed out.")
            if event_id is not None:
                record_result(event_id, status="failed", error=mapped)
            raise mapped from error
        except httpx.HTTPError as error:
            mapped = ProviderUnavailableError("Ollama local server is unavailable.")
            if event_id is not None:
                record_result(event_id, status="failed", error=mapped)
            raise mapped from error
        except Exception as error:
            if event_id is not None:
                record_result(event_id, status="failed", error=error)
            raise
        if event_id is not None:
            record_result(event_id, status="succeeded", response=_ledger_response(response_payload))
        return response_payload

    def _verify_complete(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
            raise ProviderInvalidRequestError("Ollama local response has an invalid shape.")
        prompt_count = payload.get("prompt_eval_count")
        if not isinstance(prompt_count, int) or prompt_count < 0:
            raise ProviderInvalidRequestError("Ollama local response has no prompt token count.")
        output_count = payload.get("eval_count")
        if not isinstance(output_count, int) or output_count < 0:
            raise ProviderInvalidRequestError("Ollama local response has no output token count.")
        if prompt_count >= self.num_ctx:
            raise ProviderContextLimitError(
                "Ollama prompt reached the configured context limit; no result was accepted."
            )
        if payload.get("done") is not True or payload.get("done_reason") != "stop":
            raise ProviderTruncatedResponseError(
                "Ollama did not finish generation; partial output was discarded."
            )
        content = payload["message"].get("content")
        if not isinstance(content, str):
            raise ProviderInvalidRequestError("Ollama local response has no text content.")


def _parse_json_object(content: str) -> dict[str, Any] | None:
    try:
        result = json.loads(content)
    except (TypeError, ValueError):
        return None
    return result if isinstance(result, dict) else None


def _usage(payload: dict[str, Any]) -> dict[str, int]:
    return {
        "prompt_tokens": payload["prompt_eval_count"],
        "completion_tokens": payload.get("eval_count", 0),
    }


def _ledger_response(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return {"usage": _usage(payload)} if isinstance(payload.get("prompt_eval_count"), int) else {}
