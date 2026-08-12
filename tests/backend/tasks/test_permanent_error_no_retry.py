"""Guards that permanent model errors are not autoretried.

`BaseTask` sets `autoretry_for = (Exception,)`, so every failure retries by
default. `ModelConfigurationError` is listed in `dont_autoretry_for` to opt out.
Celery wires both at task-registration time, so this is behaviour of the
generated wrapper rather than of any code in this repo, and only a real task
exercises it.
"""

import pytest

from rhesis.backend.app.utils.model_errors import (
    ModelConfigurationError,
    is_permanent_model_error,
)
from rhesis.backend.celery.core import app
from rhesis.backend.tasks.base import BaseTask


@app.task(base=BaseTask, bind=True, name="tests.permanent_error_task")
def _permanent_error_task(self):
    raise ModelConfigurationError("embedding model is not served in this region")


@app.task(base=BaseTask, bind=True, name="tests.transient_error_task")
def _transient_error_task(self):
    raise TimeoutError("upstream timed out")


class _RetryAttempted(Exception):
    """Sentinel standing in for Celery's real retry, which would re-execute."""


@pytest.fixture
def record_retries(monkeypatch):
    """Replace Task.retry so we can tell "retried" from "propagated"."""
    attempts = []

    def fake_retry(self, *args, **kwargs):
        attempts.append(kwargs)
        raise _RetryAttempted()

    monkeypatch.setattr(BaseTask, "retry", fake_retry, raising=False)
    return attempts


@pytest.mark.unit
class TestPermanentErrorNoRetry:
    def test_permanent_error_propagates_without_retrying(self, record_retries):
        """dont_autoretry_for must win over autoretry_for=(Exception,)."""
        result = _permanent_error_task.apply()

        assert isinstance(result.result, ModelConfigurationError)
        assert record_retries == [], "permanent error was retried"

    def test_transient_error_still_retries(self, record_retries):
        """The opt-out must be narrow: ordinary failures keep retrying."""
        result = _transient_error_task.apply()

        assert record_retries, "transient error was not retried"
        assert isinstance(result.result, _RetryAttempted)

    def test_dont_autoretry_for_is_declared_on_the_task(self):
        """Catches the wiring being dropped from BaseTask or the decorator."""
        assert ModelConfigurationError in _permanent_error_task.dont_autoretry_for


@pytest.mark.unit
class TestIsPermanentModelError:
    """Provider exceptions do not agree on which attribute holds the status."""

    @pytest.mark.parametrize(
        "attribute, status, expected",
        [
            # litellm / OpenAI SDK
            ("status_code", 404, True),
            ("status_code", 400, True),
            ("status_code", 401, True),
            ("status_code", 403, True),
            ("status_code", 429, False),
            ("status_code", 500, False),
            # aiohttp, raised by RhesisEmbedder against the Rhesis API
            ("status", 400, True),
            ("status", 404, True),
            ("status", 503, False),
            # google-api-core
            ("code", 404, True),
            ("code", 500, False),
        ],
    )
    def test_status_attribute_variants(self, attribute, status, expected):
        error = type("ProviderError", (Exception,), {attribute: status})()
        assert is_permanent_model_error(error) is expected

    def test_error_without_any_status_is_transient(self):
        assert is_permanent_model_error(TimeoutError("timed out")) is False

    def test_non_integer_status_is_ignored(self):
        """A string status must not be treated as a permanent HTTP code."""
        error = type("ProviderError", (Exception,), {"status_code": "404"})()
        assert is_permanent_model_error(error) is False

    def test_real_aiohttp_error_is_detected(self):
        """The concrete type RhesisEmbedder.a_generate raises."""
        import aiohttp

        error = aiohttp.ClientResponseError(
            request_info=None, history=(), status=400, message="Bad Request"
        )
        assert is_permanent_model_error(error) is True
