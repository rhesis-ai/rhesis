"""Shared model-related exceptions, and model failures as text that is safe to show."""

import asyncio
from typing import Optional

from pydantic import ValidationError

#: The one error code every model check returns when a model cannot be built.
#: Lowercase like the other codes on the wire (``quota_exceeded``, ``password_not_set``).
MODEL_NOT_CONFIGURED = "model_not_configured"

#: Where a user fixes it. Shared so every check points at the same place.
MODELS_PAGE_HINT = (
    "Open the Models page to enter a Rhesis platform API key, or add a model from your own "
    "provider."
)


class ModelConfigurationError(ValueError):
    """Raised when a model configuration is invalid or unavailable."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


def model_setup_message(purpose: str, cause: BaseException) -> str:
    """What to tell the user about a *purpose* model that can't be built.

    A ``ModelConfigurationError`` message is always our own wording, so it is passed on.
    Anything else may quote the provider, so it is replaced.
    """
    if isinstance(cause, ModelConfigurationError):
        return cause.message
    return f"No usable {purpose} model is set up. {MODELS_PAGE_HINT}"


class ModelNotConfiguredError(ValueError):
    """A model that cannot be built, worded for the user; wraps the org's own broken
    model or an unbuildable deployment default so every check reports it the same way."""

    error_code = MODEL_NOT_CONFIGURED

    def __init__(self, purpose: str, cause: BaseException):
        self.purpose = purpose
        self.cause = cause
        self.own_model = isinstance(cause, ModelConfigurationError)
        self.message = model_setup_message(purpose, cause)
        super().__init__(self.message)

    @property
    def deployment_hint(self) -> Optional[str]:
        """The env-var wording, for the deployment-default case only."""
        if self.own_model:
            return None
        return (
            f"This deployment's default {self.purpose} model could not be built. Check the "
            f"backend's DEFAULT_{self.purpose.upper()}_MODEL setting and the credentials it "
            f"needs, or set a platform key for the organization."
        )

    @property
    def log_message(self) -> str:
        hint = self.deployment_hint
        return f"{hint} Cause: {self.cause}" if hint else f"{self.message} Cause: {self.cause}"

    def detail(self, message: Optional[str] = None) -> dict:
        """The HTTP ``detail`` body. Same ``{message, error_code}`` shape the frontend
        already reads from structured details (see ``formatApiErrorDetail``)."""
        body = {"message": message or self.message, "error_code": self.error_code}
        if self.deployment_hint:
            body["deployment_hint"] = self.deployment_hint
        return body


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


_STATUS_MESSAGES = {
    401: "The provider rejected the model's credentials. Check its API key in the Models settings.",
    403: "The provider refused access to the model. Check its API key in the Models settings.",
    404: "The provider doesn't know this model. Check its name in the Models settings.",
    429: "The provider is rate-limiting this model. Try again shortly.",
}


def provider_status(error: Exception) -> Optional[int]:
    """The HTTP status a model provider attached to this failure, if any."""
    for attribute in _STATUS_ATTRIBUTES:
        status = getattr(error, attribute, None)
        if isinstance(status, int) and 400 <= status < 600:
            return status
    return None


def describe_model_error(error: Exception) -> str:
    """What went wrong with a model call, for showing or storing.

    Never reads the error's own text: a provider's message can quote the request it
    rejected, API key included. Only the exception type and the provider's HTTP status
    are used.
    """
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return "The model didn't answer in time."
    status = provider_status(error)
    # By name, so this module needs no litellm import. Its status is a plain 400.
    if type(error).__name__ == "ContextWindowExceededError":
        return "The input is too long for this model."
    if status is None and isinstance(error, ModelConfigurationError):
        return "The model isn't set up correctly. Check it in the Models settings."
    if status is None and isinstance(error, (ValidationError, ValueError)):
        return "The model's answer wasn't in the expected format."
    if status in _STATUS_MESSAGES:
        return _STATUS_MESSAGES[status]
    if status is not None and status >= 500:
        return f"The provider had an error ({status}). Try again."
    if status is not None:
        return f"The provider refused the request ({status})."
    return f"The model call failed ({type(error).__name__})."
