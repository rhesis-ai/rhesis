"""Shared model-related exceptions."""

from typing import Optional


class ModelConfigurationError(ValueError):
    """Raised when a model configuration is invalid or unavailable."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


# Provider statuses that mean "this request is wrong", not "try again later":
# bad request, missing/invalid credentials, no permission, unknown model.
_PERMANENT_PROVIDER_STATUSES = frozenset({400, 401, 403, 404})


def is_permanent_model_error(error: BaseException) -> bool:
    """Return True when a provider error cannot be resolved by retrying.

    litellm and the OpenAI SDK both attach ``status_code`` to their exceptions.
    A 404 for a model that isn't served in the configured region is the case
    this exists for: retrying it only multiplies the log noise.
    """
    status_code = getattr(error, "status_code", None)
    return isinstance(status_code, int) and status_code in _PERMANENT_PROVIDER_STATUSES
