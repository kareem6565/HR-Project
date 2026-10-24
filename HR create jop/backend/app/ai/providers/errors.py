"""Provider-independent AI provider error hierarchy.

These errors describe failures in AI provider interaction. They are kept
independent of the application/domain error hierarchy (Phase 3.1 ``ApplicationError``)
so that business/contract validation errors are never conflated with provider
failures. No retry or backoff behavior is implemented here.
"""


class ProviderError(Exception):
    """Base class for provider-independent AI provider errors."""


class ProviderConfigurationError(ProviderError):
    """The selected provider is missing required server configuration."""


class ProviderTimeoutError(ProviderError):
    """The provider call exceeded its time budget."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected the call due to rate limiting."""


class ProviderUnavailableError(ProviderError):
    """The provider is unreachable or currently unavailable."""


class ProviderInvalidRequestError(ProviderError):
    """The request was malformed or rejected as invalid by the provider."""


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
