"""Soal.help-compatible provider adapter implemented via the OpenAI Python SDK.

Soal is reached through its OpenAI-compatible gateway (``SOAL_BASE_URL``,
default ``https://soal.help/api/v1``, model ``gemini-3.5-flash``) using the
``openai`` package.

This adapter implements the provider-independent ``AIProvider`` interface only.
It performs no domain work, does not touch the database, and has no knowledge of
workflows, traces, or resume parsing. Errors are mapped onto the provider error
hierarchy in ``app.ai.providers.errors``.
"""

from __future__ import annotations

import json
import time
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from app.ai.providers.base import AIProvider, StructuredGenerationRequest, TextGenerationRequest
from app.ai.providers.errors import (
    ProviderError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.ai.results import StructuredAIResult, TextAIResult

_STRUCTURED_MAX_ATTEMPTS = 3
_STRUCTURED_RETRY_DELAY_SECONDS = 1.0
_DEFAULT_BASE_URL = "https://soal.help/api/v1"

_SYSTEM_JSON_PROMPT = (
    "You are a structured data extraction assistant. Respond with a single JSON"
    " object that conforms to the provided JSON schema, and nothing else. No"
    " commentary, no markdown code fences."
)


class SoalProvider(AIProvider):
    """Adapter around an OpenAI-compatible ``/chat/completions`` endpoint for Soal."""

    provider_name = "soal"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash",
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model_name = model
        self.base_url = base_url or _DEFAULT_BASE_URL
        self._client = OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    def generate_structured(self, request: StructuredGenerationRequest) -> StructuredAIResult:
        started = time.monotonic()
        payload = None
        data: dict[str, Any] | None = None
        transient_error: Exception | None = None
        attempts = 0
        use_response_format = request.output_schema is not None
        while True:
            attempts += 1
            try:
                payload = self._complete_chat(
                    request.input, request.output_schema, use_response_format
                )
            except ProviderInvalidRequestError as error:
                if use_response_format and _looks_like_json_format_rejection(error):
                    # Some OpenAI-compatible gateways reject `response_format`;
                    # fall back to a prompt-driven JSON schema.
                    use_response_format = False
                    attempts -= 1
                    continue
                raise
            except ProviderError:
                raise
            except Exception as error:  # noqa: BLE001 - normalize vendor/network failures
                mapped = _map_exception(error)
                if mapped is None:
                    raise ProviderUnavailableError(str(error)) from error
                if isinstance(mapped, (ProviderRateLimitError, ProviderUnavailableError)):
                    transient_error = mapped
                    if attempts >= _STRUCTURED_MAX_ATTEMPTS:
                        raise mapped from error
                    time.sleep(_STRUCTURED_RETRY_DELAY_SECONDS * attempts)
                    continue
                raise mapped from error

            if request.output_schema is None:
                break
            data = _extract_dict(_extract_content(payload))
            if data is not None or attempts >= _STRUCTURED_MAX_ATTEMPTS:
                break
            time.sleep(_STRUCTURED_RETRY_DELAY_SECONDS * attempts)

        if data is None and transient_error is not None:
            raise transient_error

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return StructuredAIResult(
            provider=self.provider_name,
            model=self.model_name,
            token_usage=_extract_token_usage(payload),
            latency_ms=elapsed_ms,
            data=data,
            schema_version=request.schema_version,
        )

    def generate_text(self, request: TextGenerationRequest) -> TextAIResult:
        started = time.monotonic()
        try:
            payload = self._complete_chat(request.input, None, use_response_format=False)
        except ProviderError:
            raise
        except Exception as error:  # noqa: BLE001 - normalize vendor/network failures
            mapped = _map_exception(error)
            if mapped is not None:
                raise mapped from error
            raise ProviderUnavailableError(str(error)) from error

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return TextAIResult(
            provider=self.provider_name,
            model=self.model_name,
            token_usage=_extract_token_usage(payload),
            latency_ms=elapsed_ms,
            text=str(_extract_content(payload) or ""),
        )

    def _complete_chat(
        self,
        input_text: str,
        output_schema: type[BaseModel] | None,
        use_response_format: bool,
    ) -> Any:
        messages: list[dict[str, Any]] = []
        if output_schema is not None:
            schema_json = json.dumps(output_schema.model_json_schema())
            messages.append(
                {"role": "system", "content": f"{_SYSTEM_JSON_PROMPT}\n\n{schema_json}"}
            )
        messages.append({"role": "user", "content": input_text})

        kwargs: dict[str, Any] = {"model": self.model_name, "messages": messages}
        if use_response_format:
            kwargs["response_format"] = {"type": "json_object"}
        return self._client.chat.completions.create(**kwargs)


def _extract_content(payload: Any) -> Any:
    """Return the assistant text content from an OpenAI conversation response."""
    if isinstance(payload, dict):
        choices = payload.get("choices") or []
        if choices:
            first = choices[0]
            message = first.get("message") or first
            content = message.get("content")
            if content is not None:
                return content
        return payload.get("content")

    choices = getattr(payload, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None) or first
        content = getattr(message, "content", None)
        if content is not None:
            return content
    return getattr(payload, "content", None)


def _extract_dict(content: Any) -> dict[str, Any] | None:
    """Return structured ``data`` as a plain dict from the response content.

    Handles content as a JSON string, a dict, a Pydantic model, or the
    list-of-parts shape returned by some OpenAI-compatible gateways.
    """
    if isinstance(content, dict):
        return dict(content)
    if isinstance(content, list):
        parts = [p.get("text") if isinstance(p, dict) else p for p in content]
        content = "".join(str(p) for p in parts if p is not None)
    if isinstance(content, str):
        text = content.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            text = text[text.find("\n") + 1 :] if "\n" in text[:8] else text
            text = text.rstrip("`").strip()
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return None
        if isinstance(parsed, dict):
            return dict(parsed)
        return None
    if isinstance(content, BaseModel):
        return content.model_dump()
    return None


def _extract_token_usage(payload: Any) -> dict[str, int] | None:
    if isinstance(payload, dict):
        usage = payload.get("usage")
    else:
        usage = getattr(payload, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return {str(k): int(v) for k, v in usage.items() if isinstance(v, int)}
    return {
        str(k): int(v)
        for k, v in vars(usage).items()
        if not k.startswith("_") and isinstance(v, int)
    }


def _looks_like_json_format_rejection(error: ProviderInvalidRequestError) -> bool:
    """True when a gateway rejects ``response_format`` (e.g. json_object)."""
    text = str(error).lower()
    return any(
        term in text
        for term in (
            "response_format",
            "response format",
            "json_object",
            "json mode",
            "parameter 'response_format'",
        )
    )


def _map_exception(error: Exception) -> ProviderError | None:
    """Best-effort mapping of vendor exceptions onto the provider error hierarchy."""
    code = None
    for attr in ("status_code", "code", "grpc_status"):
        candidate = getattr(error, attr, None)
        if candidate is not None and (isinstance(candidate, int) and candidate > 0):
            code = candidate
            break

    if code is not None:
        if code == 408 or code == 504:
            return ProviderTimeoutError(str(error))
        if code == 429:
            return ProviderRateLimitError(str(error))
        if code in (400, 401, 403, 404, 422):
            return ProviderInvalidRequestError(str(error))
        return ProviderUnavailableError(str(error))

    message = str(error).lower()
    error_type = type(error).__name__.lower()

    if any(term in message or term in error_type for term in ("timeout", "deadline exceeded")):
        return ProviderTimeoutError(str(error))
    if any(
        term in message or term in error_type
        for term in (
            "rate limit",
            "rate_limit",
            "resource exhausted",
            "resource_exhausted",
            "quota",
            "too many requests",
        )
    ):
        return ProviderRateLimitError(str(error))
    if any(
        term in message or term in error_type
        for term in ("invalid argument", "invalid request", "bad request")
    ):
        return ProviderInvalidRequestError(str(error))
    if any(
        term in message or term in error_type
        for term in (
            "unauthorized",
            "permission denied",
            "not found",
            "connection",
            "unavailable",
            "internal error",
        )
    ):
        return ProviderUnavailableError(str(error))
    return None
