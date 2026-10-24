"""Provider-independent AI result types.

These results carry only generation metadata and generic structured data. They
contain no domain objects and are never persisted by the provider layer. Fields
that may be unknown are nullable so callers can rely on them only when present.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class AIResult(BaseModel):
    """Metadata shared by all provider results."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None = None
    token_usage: dict[str, int] | None = None
    latency_ms: int | None = None


class StructuredAIResult(AIResult):
    """A structured generation result exposing generic structured data."""

    data: dict[str, Any] | None = None
    schema_version: str | None = None


class TextAIResult(AIResult):
    """A text generation result exposing generated text."""

    text: str
