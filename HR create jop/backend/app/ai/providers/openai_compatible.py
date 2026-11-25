"""Shared adapter for providers exposing OpenAI-compatible chat completions."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from app.ai.providers.base import AIProvider, StructuredGenerationRequest, TextGenerationRequest
from app.ai.providers.errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderInsufficientCreditsError,
    ProviderInvalidRequestError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderTruncatedResponseError,
    ProviderUnavailableError,
)
from app.ai.results import StructuredAIResult, TextAIResult

logger = logging.getLogger("app.ai.provider")
_SYSTEM_JSON_PROMPT = (
    "You are a structured data extraction assistant. Respond with a single JSON"
    " object that conforms to the provided JSON schema, and nothing else. No"
    " commentary, no markdown code fences."
)
_STRUCTURED_MAX_ATTEMPTS = 3
_STRUCTURED_RETRY_DELAY_SECONDS = 1.0


class OpenAICompatibleProvider(AIProvider):
    """Provider-neutral OpenAI SDK adapter; subclasses supply endpoint defaults."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 60.0,
        max_retries: int = 1,
        max_tokens: int | None = None,
        http_client: Any = None,
        self_hosted: bool = False,
    ) -> None:
        self.api_key = api_key
        self.model_name = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.self_hosted = self_hosted
        # Secure by default, including direct provider construction outside the factory.
        self.cost_policy_enabled = True
        client_options: dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": timeout,
            # Every HTTP attempt must pass the shared policy and be metered.
            "max_retries": 0,
        }
        if http_client is not None:
            client_options["http_client"] = http_client
        self._client = OpenAI(**client_options)

    def generate_structured(self, request: StructuredGenerationRequest) -> StructuredAIResult:
        started = time.monotonic()
        payload = None
        data: dict[str, Any] | None = None
        use_response_format = request.output_schema is not None
        attempts = 0
        while True:
            attempts += 1
            try:
                payload = self._complete_chat(
                    request.input,
                    request.output_schema,
                    use_response_format,
                    request.metadata,
                    request.system_prompt,
                )
            except ProviderInvalidRequestError as error:
                if use_response_format and _looks_like_json_format_rejection(error):
                    use_response_format = False
                    continue
                raise
            except ProviderInvalidResponseError:
                paid_single_shot = self.model_name == "deepseek/deepseek-v4.1-flash-1017"
                if not paid_single_shot and attempts < _STRUCTURED_MAX_ATTEMPTS:
                    time.sleep(_STRUCTURED_RETRY_DELAY_SECONDS * attempts)
                    continue
                raise
            except ProviderError:
                raise
            except Exception as error:  # noqa: BLE001 - normalize vendor/network failures
                mapped = _normalize_exception(error)
                if (
                    isinstance(mapped, ProviderInvalidRequestError)
                    and use_response_format
                    and _looks_like_json_format_rejection(mapped)
                ):
                    use_response_format = False
                    continue
                if isinstance(mapped, (ProviderRateLimitError, ProviderUnavailableError)):
                    raise mapped from error
                raise mapped from error

            if request.output_schema is None:
                break
            if _finish_reason(payload) == "length":
                raise ProviderTruncatedResponseError(
                    "The provider reached its output-token limit; partial structured output "
                    "was discarded."
                )
            data = _extract_dict(_extract_content(payload))
            if data is None:
                # The approved paid DeepSeek route is strictly single-shot to
                # keep its cost reservation bounded. Preserve the existing
                # bounded repair attempt for non-paid compatible providers.
                paid_single_shot = self.model_name == "deepseek/deepseek-v4.1-flash-1017"
                if not paid_single_shot and attempts < _STRUCTURED_MAX_ATTEMPTS:
                    time.sleep(_STRUCTURED_RETRY_DELAY_SECONDS * attempts)
                    continue
                raise ProviderInvalidResponseError(
                    "OpenRouter returned a successful response without usable structured JSON."
                )
            break

        return StructuredAIResult(
            provider=self.provider_name,
            model=self.model_name,
            token_usage=_extract_token_usage(payload),
            latency_ms=int((time.monotonic() - started) * 1000),
            data=data,
            schema_version=request.schema_version,
        )

    def generate_text(self, request: TextGenerationRequest) -> TextAIResult:
        started = time.monotonic()
        try:
            payload = self._complete_chat(
                request.input, None, use_response_format=False, metadata=request.metadata
            )
        except ProviderError:
            raise
        except Exception as error:  # noqa: BLE001 - normalize vendor/network failures
            raise _normalize_exception(error) from error
        return TextAIResult(
            provider=self.provider_name,
            model=self.model_name,
            token_usage=_extract_token_usage(payload),
            latency_ms=int((time.monotonic() - started) * 1000),
            text=str(_extract_content(payload) or ""),
        )

    def _complete_chat(
        self,
        input_text: str,
        output_schema: type[BaseModel] | None,
        use_response_format: bool,
        metadata: dict[str, Any] | None = None,
        system_prompt: str | None = None,
    ) -> Any:
        from app.ai.cost_policy import minimize_hr_identifiers, record_result

        if self.self_hosted:
            from app.ai.cost_policy import authorize_self_hosted_and_reserve
        else:
            from app.ai.cost_policy import (
                add_free_routing_constraints,
                add_paid_routing_constraints,
                authorize_and_reserve,
            )

        minimized_input = minimize_hr_identifiers(input_text)
        messages: list[dict[str, Any]] = []
        if output_schema is not None:
            schema_json = json.dumps(
                _compact_json_schema(output_schema.model_json_schema()),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            messages.append(
                {
                    "role": "system",
                    "content": f"{system_prompt or _SYSTEM_JSON_PROMPT}\n\n{schema_json}",
                }
            )
        messages.append({"role": "user", "content": minimized_input})
        prompt_characters = sum(
            len(str(message.get("content", ""))) for message in messages
        )
        kwargs: dict[str, Any] = {"model": self.model_name, "messages": messages}
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if use_response_format:
            kwargs["response_format"] = {"type": "json_object"}
        if self.cost_policy_enabled and not self.self_hosted:
            if self.model_name == "openrouter/free":
                add_free_routing_constraints(
                    kwargs, model=self.model_name, structured=output_schema is not None
                )
            elif not self.model_name.endswith(":free"):
                # The approved DeepSeek route uses one price-capped provider and no fallback.
                kwargs.setdefault("extra_body", {})["reasoning"] = {"enabled": False}
                add_paid_routing_constraints(kwargs, model=self.model_name)
        event_id = None
        if self.cost_policy_enabled:
            if self.self_hosted:
                event_id = authorize_self_hosted_and_reserve(
                    provider=self.provider_name, model=self.model_name, metadata=metadata
                )
            else:
                event_id = authorize_and_reserve(
                    provider=self.provider_name,
                    model=self.model_name,
                    base_url=self.base_url,
                    structured=output_schema is not None,
                    metadata=metadata,
                    api_key=self.api_key,
                    has_api_key=bool(self.api_key),
                    prompt_characters=prompt_characters,
                    input_bytes=len(minimized_input.encode("utf-8")),
                    max_output_tokens=self.max_tokens,
                )
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as error:
            if event_id is not None:
                record_result(
                    event_id,
                    status="failed",
                    error=_normalize_exception(error),
                    prompt_characters=prompt_characters,
                )
            raise
        if output_schema is not None and _extract_dict(_extract_content(response)) is None:
            finish_reason = _finish_reason(response)
            truncated = finish_reason in {"length", "max_tokens"}
            error_class = ProviderTruncatedResponseError if truncated else ProviderInvalidResponseError
            error = error_class(
                "OpenRouter returned a truncated structured response."
                if truncated
                else "OpenRouter returned a successful response without usable structured JSON.",
                error_code=("provider_response_truncated" if truncated else None),
                provider_status=200,
                provider_request_id=getattr(response, "id", None),
            )
            if event_id is not None:
                record_result(
                    event_id,
                    status="failed",
                    response=response,
                    error=error,
                    prompt_characters=prompt_characters,
                )
            logger.warning(
                "AI provider response could not be parsed as the requested structured output.",
                extra={
                    "phase": "response_validation",
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "error_code": error.error_code,
                    "finish_reason": finish_reason,
                    "output_tokens": _usage_count(response, "completion_tokens", "output_tokens"),
                    "provider_request_id": getattr(response, "id", None),
                },
            )
            raise error
        if event_id is not None:
            record_result(
                event_id,
                status="succeeded",
                response=response,
                prompt_characters=prompt_characters,
            )
        return response


def _extract_content(payload: Any) -> Any:
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


def _finish_reason(payload: Any) -> str | None:
    """Return the provider's bounded completion stop reason for diagnostics."""
    choices = payload.get("choices") if isinstance(payload, dict) else getattr(payload, "choices", None)
    if not choices:
        return None
    choice = choices[0]
    reason = choice.get("finish_reason") if isinstance(choice, dict) else getattr(choice, "finish_reason", None)
    return reason if isinstance(reason, str) and len(reason) <= 40 else None


def _compact_json_schema(value: Any) -> Any:
    """Drop prose-only JSON Schema annotations while preserving validation shape."""
    if isinstance(value, dict):
        return {
            key: _compact_json_schema(item)
            for key, item in value.items()
            if key not in {"title", "description", "examples", "default"}
        }
    if isinstance(value, list):
        return [_compact_json_schema(item) for item in value]
    return value


def _extract_dict(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return dict(content)
    if isinstance(content, list):
        content = "".join(
            str(p.get("text") if isinstance(p, dict) else p) for p in content if p is not None
        )
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
        return dict(parsed) if isinstance(parsed, dict) else None
    if isinstance(content, BaseModel):
        return content.model_dump()
    return None


def _extract_token_usage(payload: Any) -> dict[str, int] | None:
    usage = payload.get("usage") if isinstance(payload, dict) else getattr(payload, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return {str(k): int(v) for k, v in usage.items() if isinstance(v, int)}
    return {
        str(k): int(v)
        for k, v in vars(usage).items()
        if not k.startswith("_") and isinstance(v, int)
    }


def _usage_count(payload: Any, *names: str) -> int | None:
    usage = payload.get("usage") if isinstance(payload, dict) else getattr(payload, "usage", None)
    if isinstance(usage, dict):
        for name in names:
            if isinstance(usage.get(name), int):
                return usage[name]
    elif usage is not None:
        for name in names:
            value = getattr(usage, name, None)
            if isinstance(value, int):
                return value
    return None


def _looks_like_json_format_rejection(error: ProviderInvalidRequestError) -> bool:
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
    code = None
    for attr in ("status_code", "code", "grpc_status"):
        candidate = getattr(error, attr, None)
        if candidate is not None and isinstance(candidate, int) and candidate > 0:
            code = candidate
            break
    if code is not None:
        request_id = getattr(error, "request_id", None)
        common = {"provider_status": code, "provider_request_id": request_id}
        if code in (408, 504):
            return ProviderTimeoutError(str(error), **common)
        if code == 429:
            return ProviderRateLimitError(str(error), **common)
        if code == 402:
            return ProviderInsufficientCreditsError(str(error), **common)
        if code == 401:
            return ProviderConfigurationError(
                str(error), error_code="invalid_api_key", **common
            )
        if code == 403:
            return ProviderConfigurationError(str(error), error_code="provider_access_denied", **common)
        if code in (400, 404, 422):
            return ProviderInvalidRequestError(str(error), **common)
        return ProviderUnavailableError(str(error), **common)
    message, error_type = str(error).lower(), type(error).__name__.lower()
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


def _normalize_exception(error: Exception) -> ProviderError:
    mapped = _map_exception(error)
    if mapped is not None:
        return mapped
    return ProviderUnavailableError(
        "OpenRouter returned an unclassified provider error.",
        error_code="unclassified_provider_error",
        provider_status=getattr(error, "status_code", None),
        provider_request_id=getattr(error, "request_id", None),
    )
