"""Deterministic, in-memory fake AI provider for tests.

It never makes network calls and never touches a database. Callers configure the
exact structured payload, text, metadata, token usage, latency, or failure it
should return, so it can simulate both success and provider failures. It is
completely generic and knows nothing about any domain entity.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.ai.providers.base import (
    AIProvider,
    StructuredGenerationRequest,
    TextGenerationRequest,
)
from app.ai.providers.errors import ProviderError, provider_error_for
from app.ai.results import StructuredAIResult, TextAIResult


class FakeAIProvider(AIProvider):
    """Configurable fake provider that returns caller-configured data."""

    def __init__(
        self,
        *,
        provider: str = "fake",
        model: str | None = None,
        structured_payload: dict[str, Any] | None = None,
        text: str = "",
        token_usage: dict[str, int] | None = None,
        latency_ms: int | None = None,
        failure: ProviderError | None = None,
        failure_kind: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._structured_payload = structured_payload
        self._text = text
        self._token_usage = token_usage
        self._latency_ms = latency_ms
        if failure is not None and failure_kind is not None:
            raise ValueError("failure and failure_kind are mutually exclusive.")
        self._failure: ProviderError | None = failure
        if failure is None and failure_kind is not None:
            self._failure = provider_error_for(failure_kind)("provider call failed")

    def clear_failure(self) -> None:
        """Clear any configured failure so subsequent calls succeed."""
        self._failure = None

    def generate_structured(self, request: StructuredGenerationRequest) -> StructuredAIResult:
        if self._failure is not None:
            raise self._failure
        return StructuredAIResult(
            provider=self._provider,
            model=self._model,
            data=deepcopy(self._structured_payload),
            schema_version=request.schema_version,
            token_usage=deepcopy(self._token_usage),
            latency_ms=self._latency_ms,
        )

    def generate_text(self, request: TextGenerationRequest) -> TextAIResult:
        if self._failure is not None:
            raise self._failure
        return TextAIResult(
            provider=self._provider,
            model=self._model,
            text=self._text,
            token_usage=deepcopy(self._token_usage),
            latency_ms=self._latency_ms,
        )
