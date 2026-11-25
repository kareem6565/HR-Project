"""Provider-independent AI provider error hierarchy.

These errors describe failures in AI provider interaction. They are kept
independent of the application/domain error hierarchy (Phase 3.1 ``ApplicationError``)
so that business/contract validation errors are never conflated with provider
failures. No retry or backoff behavior is implemented here.
"""


class ProviderError(Exception):
    """Base class for provider-independent AI provider errors."""

    error_code = "provider_error"
    stage = "provider"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        stage: str | None = None,
        retryable: bool | None = None,
        provider_status: int | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code or type(self).error_code
        self.stage = stage or type(self).stage
        self.retryable = type(self).retryable if retryable is None else retryable
        self.provider_status = provider_status
        self.provider_request_id = provider_request_id

    @property
    def safe_message(self) -> str:
        """Stable user-facing explanation that never includes provider payloads."""
        return _SAFE_MESSAGES.get(self.error_code, "The AI request failed. Try again.")


class ProviderConfigurationError(ProviderError):
    """The selected provider is missing required server configuration."""

    error_code = "configuration_error"
    stage = "preflight"


class ProviderTimeoutError(ProviderError):
    """The provider call exceeded its time budget."""

    error_code = "provider_timeout"
    retryable = True


class ProviderRateLimitError(ProviderError):
    """The provider rejected the call due to rate limiting."""

    error_code = "provider_rate_limit"
    retryable = True


class ProviderInsufficientCreditsError(ProviderError):
    """The provider key has insufficient credits or has reached its spend limit."""

    error_code = "provider_credits_exhausted"


class ProviderUnavailableError(ProviderError):
    """The provider is unreachable or currently unavailable."""

    error_code = "provider_unavailable"
    retryable = True


class ProviderInvalidRequestError(ProviderError):
    """The request was malformed or rejected as invalid by the provider."""

    error_code = "provider_rejected_request"


class ProviderBudgetExceededError(ProviderError):
    """The app's configured test spend allowance would be exceeded."""

    error_code = "app_test_budget_exceeded"
    stage = "preflight"


class ProviderInvalidResponseError(ProviderError):
    """The provider returned a response that cannot be used by the workflow."""

    error_code = "invalid_structured_response"


class ProviderUsageCheckError(ProviderUnavailableError):
    """OpenRouter usage could not be read, so a paid request was not sent."""

    error_code = "provider_usage_check_failed"
    stage = "preflight"


_SAFE_MESSAGES = {
    "configuration_error": "AI is not configured. Check the selected provider and API key.",
    "missing_api_key": "The OpenRouter API key is missing; no AI request was sent.",
    "invalid_api_key": "OpenRouter rejected the API key. Check the key configuration.",
    "provider_access_denied": "OpenRouter denied access to this model or account.",
    "usage_baseline_mismatch": "OpenRouter usage does not match the configured test baseline; no request was sent.",
    "provider_timeout": "OpenRouter took too long to respond. Try again later.",
    "provider_rate_limit": "OpenRouter is rate-limiting requests. Try again shortly.",
    "provider_credits_exhausted": "The OpenRouter key reached its provider spending limit.",
    "provider_unavailable": "OpenRouter is temporarily unavailable. Try again shortly.",
    "unclassified_provider_error": "OpenRouter returned an unexpected error. Use the request ID to find its trace.",
    "provider_rejected_request": "OpenRouter rejected this AI request. Check the model and request configuration.",
    "app_test_budget_exceeded": "This request would exceed the app's approved AI test budget; no request was sent.",
    "invalid_structured_response": "OpenRouter replied, but the response was incomplete or could not be parsed.",
    "provider_response_truncated": "OpenRouter cut off its response before finishing. Try again; if it repeats, shorten the job description.",
    "provider_usage_check_failed": "Could not check OpenRouter usage, so no AI request was sent.",
    "provider_pricing_unavailable": "Could not verify the model price, so no AI request was sent.",
    "ai_metering_unavailable": "AI usage tracking is unavailable, so no AI request was sent.",
    "app_rate_limit": "The development AI request rate limit was reached. Try again shortly.",
    "cost_guard_paused": "AI requests are paused by the spend-safety monitor. Check the latest AI event before retrying.",
    "in_flight_cost_unknown": "A previous AI request has unknown final usage. Check its AI event before retrying.",
    "provider_error": "The AI request failed. Try again.",
}


class ProviderContextLimitError(ProviderError):
    """The prompt reached the configured context limit; no generated result is usable."""


class ProviderTruncatedResponseError(ProviderError):
    """The provider did not finish generation; partial output is never returned."""


_PROVIDER_ERROR_CLASSES = {
    "timeout": ProviderTimeoutError,
    "rate_limit": ProviderRateLimitError,
    "unavailable": ProviderUnavailableError,
    "invalid_request": ProviderInvalidRequestError,
}


def provider_error_for(kind: str) -> type[ProviderError]:
    """Return the provider error class for a normalized failure kind."""
    try:
        return _PROVIDER_ERROR_CLASSES[kind]
    except KeyError as error:
        raise ValueError(f"Unknown provider failure kind: {kind!r}.") from error
