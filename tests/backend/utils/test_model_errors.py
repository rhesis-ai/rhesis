"""describe_model_error: model failures as text that never includes the provider's message."""

import asyncio

import pytest
from pydantic import BaseModel, ValidationError

from rhesis.backend.app.utils.model_errors import (
    ModelConfigurationError,
    describe_model_error,
    model_setup_message,
)

KEY = "sk-live-0123456789abcdefSECRET"


class ProviderError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _validation_error() -> ValidationError:
    class Answer(BaseModel):
        verdict: int

    try:
        Answer.model_validate({"verdict": KEY})
    except ValidationError as e:
        return e
    raise AssertionError("expected a ValidationError")


def _context_window_error() -> Exception:
    from litellm import ContextWindowExceededError

    return ContextWindowExceededError(
        message=f"maximum context length exceeded for key {KEY}", model="m", llm_provider="openai"
    )


@pytest.mark.parametrize(
    "error, expected",
    [
        (ProviderError(f"Incorrect API key provided: {KEY}", 401), "credentials"),
        (ProviderError(f"Forbidden for key {KEY}", 403), "refused access"),
        (ProviderError(f"model not found ({KEY})", 404), "doesn't know this model"),
        (ProviderError(f"rate limited for {KEY}", 429), "rate-limiting"),
        (ProviderError(f"upstream failed: {KEY}", 503), "provider had an error (503)"),
        (ProviderError(f"bad request: {KEY}", 400), "refused the request (400)"),
        (asyncio.TimeoutError(), "didn't answer in time"),
        (_validation_error(), "expected format"),
        (ValueError(f"invalid JSON: {KEY}"), "expected format"),
        (ModelConfigurationError(f"User model initialization failed: {KEY}"), "set up correctly"),
        (RuntimeError(f"Authorization: Bearer {KEY}"), "failed (RuntimeError)"),
        (_context_window_error(), "too long for this model"),
    ],
)
def test_describes_the_failure_without_the_providers_text(error, expected):
    description = describe_model_error(error)

    assert expected in description
    assert KEY not in description
    assert "SECRET" not in description


def test_setup_message_passes_on_our_own_wording():
    cause = ModelConfigurationError("Your configured model 'Mine' needs an API key.")

    assert model_setup_message("evaluation", cause) == cause.message


def test_setup_message_replaces_anything_else():
    message = model_setup_message("generation", ValueError(f"RHESIS_API_KEY={KEY}"))

    assert message.startswith("No usable generation model is set up.")
    assert KEY not in message
