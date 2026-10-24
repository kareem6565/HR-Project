"""AI-provider settings management endpoints.

These endpoints let administrators view and verify the active AI provider
configuration. Credentials are operator-managed through backend environment
variables and are never returned by the API.

Security notes:
- The configured key is never echoed back. Responses report only whether a key
  is present and where it came from (``runtime`` / ``environment`` / ``none``).
- The environment key is never echoed to clients, by design.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.providers import ProviderError, ProviderRateLimitError
from app.ai.providers.base import TextGenerationRequest
from app.ai.providers.factory import resolve_ai_config
from app.ai.providers.ollama_cloud import OllamaCloudProvider
from app.ai.providers.soal import SoalProvider
from app.api.v1.deps import RequestContext, require_roles
from app.api.v1.schemas.ai_settings import (
    AISettingsResponse,
    SetApiKeyRequest,
    VerifyApiKeyRequest,
    VerifyApiKeyResponse,
)
from app.core.config import settings

router = APIRouter()

_VERIFY_PROMPT = "Reply with exactly: OK"


@router.get("/settings/ai", response_model=AISettingsResponse)
def get_ai_settings(_: RequestContext = Depends(require_roles("admin"))) -> AISettingsResponse:
    """Return the active AI provider configuration (never the key itself).

    Restricted to organization administrators. AI configuration is operator-managed
    via environment variables.
    """
    config = resolve_ai_config(settings)
    return AISettingsResponse(
        provider=config["provider"],
        model=config["model"],
        api_key_source=config["api_key_source"],
        has_api_key=bool(config["api_key"]),
    )


@router.post("/settings/ai/api-key", response_model=AISettingsResponse)
def set_ai_api_key(
    body: SetApiKeyRequest, _: RequestContext = Depends(require_roles("admin"))
) -> AISettingsResponse:
    """Disabled: Process-wide runtime API key modification is disabled.

    AI provider credentials must be configured by system operators via environment
    variables to prevent cross-tenant interference.
    """
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Runtime AI key modification is disabled. AI provider credentials must be configured by system operators via environment variables.",
    )


@router.delete("/settings/ai/api-key", response_model=AISettingsResponse)
def clear_ai_api_key(_: RequestContext = Depends(require_roles("admin"))) -> AISettingsResponse:
    """Disabled: Process-wide runtime API key modification is disabled.

    AI provider credentials must be configured by system operators via environment
    variables to prevent cross-tenant interference.
    """
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Runtime AI key modification is disabled. AI provider credentials must be configured by system operators via environment variables.",
    )


@router.post("/settings/ai/verify", response_model=VerifyApiKeyResponse)
def verify_ai_api_key(
    body: VerifyApiKeyRequest | None = None, _: RequestContext = Depends(require_roles("admin"))
) -> VerifyApiKeyResponse:
    """Validate an API key with a minimal live call.

    Accepts an optional ``api_key`` body to test a prospective key without
    modifying server configuration. When omitted, the active environment key
    is verified. Returns ``ok=True`` on success and a short human-readable
    diagnostic on failure instead of raising, so the frontend can surface a
    friendly inline message. Never exposes secrets in responses or logs.
    """
    config = resolve_ai_config(settings)
    api_key = body.api_key.strip() if body and body.api_key else config["api_key"]
    model = config["model"] or (
        settings.soal_model if settings.ai_provider == "soal" else settings.ollama_model
    )

    if not api_key:
        return VerifyApiKeyResponse(ok=False, message="No API key configured.", model=model)

    provider_type = {
        "soal": SoalProvider,
        "ollama": OllamaCloudProvider,
    }.get(config["provider"])
    if provider_type is None:
        return VerifyApiKeyResponse(
            ok=False,
            message="Select a live AI provider before verifying an API key.",
            model=model,
        )
    provider = provider_type(
        api_key=api_key,
        model=model,
        base_url=config["base_url"]
        or (settings.soal_base_url if config["provider"] == "soal" else settings.ollama_base_url),
    )
    started = time.monotonic()
    try:
        result = provider.generate_text(TextGenerationRequest(input=_VERIFY_PROMPT))
    except ProviderRateLimitError:
        return VerifyApiKeyResponse(
            ok=False,
            message="Rate limit reached. Try again later or use another key.",
            model=model,
        )
    except ProviderError as error:  # noqa: BLE001 - map provider failures to a friendly message
        return VerifyApiKeyResponse(
            ok=False,
            message=f"Could not reach the AI provider: {type(error).__name__}.",
            model=model,
        )
    except Exception as error:  # noqa: BLE001 - last-resort guard, never 500 the request
        return VerifyApiKeyResponse(
            ok=False,
            message=f"Unexpected verification failure: {type(error).__name__}.",
            model=model,
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if not result.text or "OK" not in result.text.upper():
        return VerifyApiKeyResponse(
            ok=False,
            message="The provider responded, but with an unexpected payload.",
            model=model,
        )
    return VerifyApiKeyResponse(
        ok=True,
        message=f"Key verified — {model} responded in {elapsed_ms} ms.",
        model=model,
    )
