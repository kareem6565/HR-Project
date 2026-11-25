"""Select the configured provider; all live providers receive the free-first guard.

Explicit fake mode remains available to tests and offline development. A missing
provider key raises a configuration error rather than silently selecting Fake.
"""

from __future__ import annotations

from app.ai.providers.base import AIProvider
from app.ai.providers.errors import ProviderConfigurationError
from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.local import LocalProvider
from app.ai.providers.ollama_cloud import OllamaCloudProvider
from app.ai.providers.ollama_local import OllamaLocalProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.providers.soal import SoalProvider
from app.core.config import Settings

API_KEY_SOURCE_NONE = "none"
API_KEY_SOURCE_ENVIRONMENT = "environment"


def resolve_ai_config(settings: Settings) -> dict:
    """Return the effective provider config as a dict.

    Keys:
    - ``provider``: selected provider id, including distinct self-hosted adapters
    - ``model``: the active model ("" when fake)
    - ``base_url``: the active endpoint ("" when fake)
    - ``api_key``: the active API key ("" when none)
    - ``api_key_source``: "environment" or "none"
    - ``is_fake``: True only when the deterministic fake provider is active
    """
    if settings.ai_provider == "soal":
        api_key = settings.soal_api_key
        return {
            "provider": "soal",
            "model": settings.soal_model,
            "base_url": settings.soal_base_url,
            "api_key": api_key,
            "api_key_source": API_KEY_SOURCE_ENVIRONMENT if api_key else API_KEY_SOURCE_NONE,
            "is_fake": False,
        }
    if settings.ai_provider == "ollama":
        return {
            "provider": "ollama",
            "model": settings.ollama_model,
            "base_url": settings.ollama_base_url,
            "api_key": settings.ollama_api_key or "",
            "api_key_source": API_KEY_SOURCE_ENVIRONMENT
            if settings.ollama_api_key
            else API_KEY_SOURCE_NONE,
            "is_fake": False,
        }
    if settings.ai_provider == "local":
        return {
            "provider": "local",
            "model": settings.local_llm_model,
            "base_url": settings.local_llm_base_url,
            "api_key": settings.local_llm_api_key or "",
            "api_key_source": API_KEY_SOURCE_ENVIRONMENT
            if settings.local_llm_api_key
            else API_KEY_SOURCE_NONE,
            "is_fake": False,
        }
    if settings.ai_provider == "ollama_local":
        return {
            "provider": "ollama_local",
            "model": settings.ollama_local_model,
            "base_url": settings.ollama_local_base_url,
            "api_key": "",
            "api_key_source": API_KEY_SOURCE_NONE,
            "is_fake": False,
        }
    if settings.ai_provider == "openrouter":
        return {
            "provider": "openrouter",
            "model": settings.openrouter_model,
            "base_url": settings.openrouter_base_url,
            "api_key": settings.openrouter_api_key or "",
            "api_key_source": API_KEY_SOURCE_ENVIRONMENT
            if settings.openrouter_api_key
            else API_KEY_SOURCE_NONE,
            "is_fake": False,
        }
    if settings.ai_provider == "fake":
        return {
            "provider": "fake",
            "model": "",
            "base_url": "",
            "api_key": "",
            "api_key_source": API_KEY_SOURCE_NONE,
            "is_fake": True,
        }
    raise ValueError(f"Unsupported AI provider: {settings.ai_provider!r}.")


def get_provider(settings: Settings, **fake_kwargs) -> AIProvider:
    """Return the configured provider, requiring credentials for live providers."""
    config = resolve_ai_config(settings)
    if config["provider"] == "soal":
        if not config["api_key"]:
            raise ProviderConfigurationError("SOAL_API_KEY is required when AI_PROVIDER=soal.")
        provider = SoalProvider(
            api_key=config["api_key"],
            model=config["model"],
            base_url=config["base_url"],
        )
        provider.cost_policy_enabled = True
        return provider
    if config["provider"] == "ollama":
        if not config["api_key"]:
            raise ProviderConfigurationError("OLLAMA_API_KEY is required when AI_PROVIDER=ollama.")
        provider = OllamaCloudProvider(
            api_key=config["api_key"],
            model=config["model"],
            base_url=config["base_url"],
        )
        provider.cost_policy_enabled = True
        return provider
    if config["provider"] == "openrouter":
        if not config["api_key"]:
            raise ProviderConfigurationError(
                "OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter.",
                error_code="missing_api_key",
                stage="preflight",
            )
        provider = OpenRouterProvider(
            api_key=config["api_key"],
            model=config["model"],
            base_url=config["base_url"],
            max_tokens=settings.openrouter_max_tokens,
        )
        provider.cost_policy_enabled = True
        return provider
    if config["provider"] == "local":
        if not config["model"]:
            raise ProviderConfigurationError("LOCAL_LLM_MODEL is required when AI_PROVIDER=local.")
        provider = LocalProvider(
            api_key=config["api_key"] or None,
            model=config["model"],
            base_url=config["base_url"],
        )
        provider.cost_policy_enabled = True
        return provider
    if config["provider"] == "ollama_local":
        if not config["model"]:
            raise ProviderConfigurationError(
                "OLLAMA_LOCAL_MODEL is required when AI_PROVIDER=ollama_local."
            )
        provider = OllamaLocalProvider(
            model=config["model"],
            base_url=config["base_url"],
            num_ctx=settings.ollama_local_num_ctx,
        )
        provider.cost_policy_enabled = True
        return provider
    return FakeAIProvider(**fake_kwargs)
