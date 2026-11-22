"""Provider implementations.

``OllamaCloudProvider`` is the default live adapter; ``SoalProvider`` remains
available as an alternative, and ``FakeAIProvider`` supports offline tests.
Provider selection is handled through ``get_provider``.
"""

from app.ai.providers.base import (
    AIProvider,
    StructuredGenerationRequest,
    TextGenerationRequest,
)
from app.ai.providers.errors import (
    ProviderConfigurationError,
    ProviderContextLimitError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderTruncatedResponseError,
    ProviderUnavailableError,
    provider_error_for,
)
from app.ai.providers.factory import get_provider
from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.local import LocalProvider
from app.ai.providers.ollama_cloud import OllamaCloudProvider
from app.ai.providers.ollama_local import OllamaLocalProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.providers.soal import SoalProvider

__all__ = [
    "AIProvider",
    "FakeAIProvider",
    "OllamaCloudProvider",
    "OllamaLocalProvider",
    "LocalProvider",
    "OpenAICompatibleProvider",
    "OpenRouterProvider",
    "SoalProvider",
    "ProviderError",
    "ProviderConfigurationError",
    "ProviderContextLimitError",
    "ProviderInvalidRequestError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderTruncatedResponseError",
    "ProviderUnavailableError",
    "StructuredGenerationRequest",
    "TextGenerationRequest",
    "get_provider",
    "provider_error_for",
]
