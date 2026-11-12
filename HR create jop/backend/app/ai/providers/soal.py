"""Soal provider defaults backed by HERA's shared OpenAI-compatible adapter."""

from __future__ import annotations

from app.ai.providers.openai_compatible import OpenAICompatibleProvider

_DEFAULT_BASE_URL = "https://soal.help/api/v1"


class SoalProvider(OpenAICompatibleProvider):
    """Soal.help gateway adapter; public constructor remains backward compatible."""

    provider_name = "soal"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash",
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 1,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or _DEFAULT_BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
            max_tokens=max_tokens,
        )
