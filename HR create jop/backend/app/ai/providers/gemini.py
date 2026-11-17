"""Google Gemini adapter using Google's OpenAI-compatible API endpoint."""

from __future__ import annotations

from app.ai.providers.soal import SoalProvider


class GeminiProvider(SoalProvider):
    """Gemini API provider with Gemini-specific identity and defaults."""

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.8-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
