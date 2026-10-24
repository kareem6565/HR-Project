"""Provider-independent AI provider interface and request contracts.

The interface defines only AI interaction semantics: structured generation and
text generation. It does not depend on any specific LLM vendor, on SQLAlchemy,
FastAPI, or on domain services, and it does not persist anything.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.ai.contracts.schema import AI_CONTRACT_SCHEMA_VERSION
from app.ai.results import StructuredAIResult, TextAIResult


class StructuredGenerationRequest(BaseModel):
    """A request for structured generation."""

    model_config = ConfigDict(extra="forbid")

    input: str
    output_schema: type[BaseModel] | None = None
    schema_version: str = AI_CONTRACT_SCHEMA_VERSION
    metadata: dict[str, Any] | None = None


class TextGenerationRequest(BaseModel):
    """A request for plain text generation."""

    model_config = ConfigDict(extra="forbid")

    input: str
    metadata: dict[str, Any] | None = None


class AIProvider(ABC):
    """Provider-independent interface for AI generation."""

    @abstractmethod
    def generate_structured(self, request: StructuredGenerationRequest) -> StructuredAIResult:
        """Generate structured data for the given request."""

    @abstractmethod
    def generate_text(self, request: TextGenerationRequest) -> TextAIResult:
        """Generate free-form text for the given request."""
