"""Tests for async endpoint invocation retry logic."""

import pytest

from rhesis.backend.app.services.invokers.common.errors import (
    EndpointInvocationError,
    classify_error_response,
)
from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse
from rhesis.backend.tasks.execution.batch.retry import invoke_with_retry

FAST = dict(min_wait=0.001, max_wait=0.01)


class TestEndpointInvocationError:
    def test_transient_flag(self):
        err = EndpointInvocationError("timeout", transient=True, status_code=504)
        assert err.transient is True
        assert err.status_code == 504

    def test_permanent_flag(self):
        err = EndpointInvocationError("bad request", transient=False, status_code=400)
        assert err.transient is False


class TestClassifyErrorResponse:
    def test_429_is_transient(self):
        resp = ErrorResponse(
            output="Rate limited",
            error_type="http_error",
            message="rate limit",
            status_code=429,
            response_headers={"Retry-After": "5"},
        )
        err = classify_error_response(resp)
        assert err.transient is True
        assert err.retry_after == 5.0
        assert err.status_code == 429

    def test_503_is_transient(self):
        resp = ErrorResponse(
            output="Service unavailable",
            error_type="http_error",
            message="unavailable",
            status_code=503,
        )
        err = classify_error_response(resp)
        assert err.transient is True

    def test_400_is_permanent(self):
        resp = ErrorResponse(
            output="Bad request",
            error_type="http_error",
            message="bad input",
            status_code=400,
        )
        err = classify_error_response(resp)
        assert err.transient is False

    def test_network_error_type_is_transient(self):
        resp = ErrorResponse(
            output="Connection refused",
            error_type="network_error",
            message="conn refused",
        )
        err = classify_error_response(resp)
        assert err.transient is True

    def test_timeout_error_type_is_transient(self):
        resp = ErrorResponse(
            output="Timed out",
            error_type="timeout_error",
            message="request timed out",
        )
        err = classify_error_response(resp)
        assert err.transient is True


class TestInvokeWithRetry:
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        calls = []

        async def _factory():
            calls.append(1)
            return {"output": "ok"}

        result = await invoke_with_retry(_factory, max_attempts=3, **FAST)
        assert result == {"output": "ok"}
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_retries_transient_then_succeeds(self):
        call_count = 0

        async def _factory():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise EndpointInvocationError(
                    "gateway timeout", transient=True, status_code=504,
                )
            return {"output": "ok"}

        result = await invoke_with_retry(_factory, max_attempts=4, **FAST)
        assert result == {"output": "ok"}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_permanent_error_not_retried(self):
        calls = []

        async def _factory():
            calls.append(1)
            raise EndpointInvocationError(
                "bad request", transient=False, status_code=400,
            )

        with pytest.raises(EndpointInvocationError) as exc_info:
            await invoke_with_retry(_factory, max_attempts=4, **FAST)

        assert exc_info.value.transient is False
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_exhausts_retries_on_transient(self):
        calls = []

        async def _factory():
            calls.append(1)
            raise EndpointInvocationError(
                "always fails", transient=True, status_code=503,
            )

        with pytest.raises(EndpointInvocationError) as exc_info:
            await invoke_with_retry(_factory, max_attempts=3, **FAST)

        assert exc_info.value.transient is True
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_error_response_is_classified_and_retried(self):
        call_count = 0

        async def _factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ErrorResponse(
                    output="Rate limited",
                    error_type="http_error",
                    message="rate limit",
                    status_code=429,
                )
            return {"output": "ok"}

        result = await invoke_with_retry(_factory, max_attempts=3, **FAST)
        assert result == {"output": "ok"}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_permanent_error_response_not_retried(self):
        calls = []

        async def _factory():
            calls.append(1)
            return ErrorResponse(
                output="Bad request",
                error_type="http_error",
                message="invalid json",
                status_code=400,
            )

        with pytest.raises(EndpointInvocationError) as exc_info:
            await invoke_with_retry(_factory, max_attempts=3, **FAST)

        assert exc_info.value.transient is False
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_connection_error_is_retried(self):
        call_count = 0

        async def _factory():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("refused")
            return {"output": "ok"}

        result = await invoke_with_retry(_factory, max_attempts=3, **FAST)
        assert result == {"output": "ok"}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_error_is_retried(self):
        call_count = 0

        async def _factory():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("deadline exceeded")
            return {"output": "ok"}

        result = await invoke_with_retry(_factory, max_attempts=3, **FAST)
        assert result == {"output": "ok"}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_value_error_not_retried(self):
        calls = []

        async def _factory():
            calls.append(1)
            raise ValueError("bad input")

        with pytest.raises(ValueError):
            await invoke_with_retry(_factory, max_attempts=3, **FAST)

        assert len(calls) == 1
