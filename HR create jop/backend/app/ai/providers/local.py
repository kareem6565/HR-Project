"""Self-hosted OpenAI-compatible adapter for vLLM, LM Studio, and similar servers."""

from __future__ import annotations

from typing import Any

from app.ai.providers.openai_compatible import OpenAICompatibleProvider


class LocalProvider(OpenAICompatibleProvider):
    """OpenAI-compatible self-hosted server; independent from Ollama Cloud."""

    provider_name = "local"

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 1,
        max_tokens: int | None = None,
        http_client: Any = None,
    ) -> None:
        super().__init__(
            api_key=api_key or "self-hosted",
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_tokens=max_tokens,
            http_client=http_client,
            self_hosted=True,
        )
