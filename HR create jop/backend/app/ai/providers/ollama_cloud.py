"""Ollama Cloud adapter using HERA's existing OpenAI-compatible provider client."""

from __future__ import annotations

from app.ai.providers.soal import SoalProvider


class OllamaCloudProvider(SoalProvider):
    """OpenAI-compatible Ollama Cloud provider with its documented endpoint defaults."""

    provider_name = "ollama"

    def __init__(
        self,
        api_key: str,
        model: str = "gemma4:31b",
        base_url: str = "https://ollama.com/v1",
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
