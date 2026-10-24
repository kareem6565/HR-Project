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
    ProviderError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    provider_error_for,
)
from app.ai.providers.factory import get_provider
from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.ollama_cloud import OllamaCloudProvider
from app.ai.providers.soal import SoalProvider

__all__ = [
    "AIProvider",
    "FakeAIProvider",
    "OllamaCloudProvider",
    "SoalProvider",
    "ProviderError",
    "ProviderConfigurationError",
    "ProviderInvalidRequestError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "StructuredGenerationRequest",
    "TextGenerationRequest",
    "get_provider",
    "provider_error_for",
]
