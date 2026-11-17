"""Provider implementations.

``OllamaCloudProvider``, ``SoalProvider``, and ``GeminiProvider`` are available
live adapters; ``FakeAIProvider`` supports offline use.
Provider selection is handled through ``get_provider``.
"""

from app.ai.providers.base import (
    AIProvider,
    StructuredGenerationRequest,
    TextGenerationRequest,
)
from app.ai.providers.errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderInsufficientCreditsError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    provider_error_for,
)
from app.ai.providers.factory import get_provider
from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.ollama_cloud import OllamaCloudProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.providers.soal import SoalProvider

__all__ = [
    "AIProvider",
    "FakeAIProvider",
    "GeminiProvider",
    "OllamaCloudProvider",
    "OpenRouterProvider",
    "SoalProvider",
    "ProviderError",
    "ProviderConfigurationError",
    "ProviderInvalidRequestError",
    "ProviderInsufficientCreditsError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "StructuredGenerationRequest",
    "TextGenerationRequest",
    "get_provider",
    "provider_error_for",
]
