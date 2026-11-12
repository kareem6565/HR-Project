"""OpenRouter adapter using the existing OpenAI-compatible provider client."""

from __future__ import annotations

from app.ai.providers.openai_compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter Chat Completions provider with OpenRouter defaults."""

    provider_name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek/deepseek-v4.1-flash-1017",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
        max_retries: int = 1,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_tokens=max_tokens,
        )
