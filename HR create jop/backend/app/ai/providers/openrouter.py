"""OpenRouter adapter using its OpenAI-compatible chat completions API."""

from __future__ import annotations

from app.ai.providers.soal import SoalProvider


class OpenRouterProvider(SoalProvider):
    """OpenRouter provider with model routing through an OpenRouter model slug."""

    provider_name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek/deepseek-v4.1-flash-1017:nitro",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
        max_retries: int = 1,
        max_tokens: int = 1024,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_tokens=max_tokens,
        )
