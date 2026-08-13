"""Shared model-related exceptions."""

from typing import Optional


class ModelConfigurationError(ValueError):
    """Raised when a model configuration is invalid or unavailable."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class EmbeddingProviderNotConfigured(ModelConfigurationError):
    """No real embedding provider is configured for this deployment.

    Distinct from a provider that *is* configured but broken (bad key,
    inaccessible model): that stays a plain ``ModelConfigurationError`` and
    should still fail loudly. This one means ``DEFAULT_EMBEDDING_MODEL`` still
    resolves to the Rhesis native provider, whose ``.generate()`` would call
    this backend's own embedding endpoint over HTTP -- i.e. itself.

    Subclasses ``ModelConfigurationError`` so existing handlers keep catching
    it; callers that can degrade gracefully (embeddings are optional
    enrichment) catch this narrower type and carry on without vectors.
    """


# Provider statuses that mean "this request is wrong", not "try again later":
# bad request, missing/invalid credentials, no permission, unknown model.
_PERMANENT_PROVIDER_STATUSES = frozenset({400, 401, 403, 404})

# Attribute names carrying an HTTP status, in priority order. No single name
# covers our providers: litellm and the OpenAI SDK use ``status_code``, aiohttp
# (raised by RhesisEmbedder) uses ``status``, and google-api-core uses ``code``.
# ``code`` is last because aiohttp also defines it as a deprecated alias, and
# reaching it would emit a DeprecationWarning.
_STATUS_ATTRIBUTES = ("status_code", "status", "code")


def is_permanent_model_error(error: BaseException) -> bool:
    """Return True when a provider error cannot be resolved by retrying.

    A 404 for a model that isn't served in the configured region is the case
    this exists for: retrying it only multiplies the log noise.

    Only integer values in :data:`_PERMANENT_PROVIDER_STATUSES` count, so an
    unrelated attribute of the same name cannot accidentally mark a transient
    failure permanent.
    """
    for attribute in _STATUS_ATTRIBUTES:
        status = getattr(error, attribute, None)
        if isinstance(status, int):
            return status in _PERMANENT_PROVIDER_STATUSES
    return False
