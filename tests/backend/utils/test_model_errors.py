"""describe_model_error: model failures as text that never includes the provider's message."""

import asyncio

import pytest
from pydantic import BaseModel, ValidationError

from rhesis.backend.app.utils.model_errors import ModelConfigurationError, describe_model_error

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
    ],
)
def test_describes_the_failure_without_the_providers_text(error, expected):
    description = describe_model_error(error)

    assert expected in description
    assert KEY not in description
    assert "SECRET" not in description
