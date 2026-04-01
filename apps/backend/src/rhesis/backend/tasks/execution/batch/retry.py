"""Async retry helper for endpoint invocations (tenacity-based).

Provides ``invoke_with_retry`` which wraps an async callable with
exponential backoff + jitter, classifying errors as transient or
permanent so that only recoverable failures are retried.
"""

import logging
from typing import Any, Callable, Coroutine

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from rhesis.backend.app.services.invokers.common.errors import (
    EndpointInvocationError,
    classify_error_response,
)

logger = logging.getLogger(__name__)


def _is_transient(exc: BaseException) -> bool:
    """Return ``True`` for exceptions that should trigger a retry."""
    if isinstance(exc, EndpointInvocationError):
        return exc.transient
    return isinstance(exc, (TimeoutError, ConnectionError, OSError))


def _log_before_retry(label: str) -> Callable[[RetryCallState], None]:
    """Return a tenacity ``before_sleep`` callback that logs retry info."""
    def _callback(retry_state: RetryCallState) -> None:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        attempt = retry_state.attempt_number
        wait = retry_state.next_action.sleep if retry_state.next_action else 0

        if isinstance(exc, EndpointInvocationError):
            logger.warning(
                "[%s] transient failure (attempt %d), retrying in %.1fs: %s "
                "(status=%s, type=%s)",
                label, attempt, wait, exc,
                exc.status_code, exc.error_type,
            )
        else:
            logger.warning(
                "[%s] transient failure (attempt %d), retrying in %.1fs: %s",
                label, attempt, wait, exc,
            )

    return _callback


async def invoke_with_retry(
    coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    *,
    max_attempts: int = 4,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    label: str = "invoke_endpoint",
) -> Any:
    """Call *coro_factory* up to *max_attempts* times with exponential backoff.

    ``coro_factory`` must be a zero-arg callable that returns a fresh
    coroutine on each call (a lambda or closure is fine).

    The function retries when it catches an ``EndpointInvocationError``
    with ``transient=True``, or a recognised transient stdlib exception
    (``TimeoutError``, ``ConnectionError``, ``OSError``).

    If the coroutine returns an ``ErrorResponse`` (the invoker signals
    an endpoint-level error without raising), the response is classified
    and raised as ``EndpointInvocationError`` so the same retry logic
    applies.

    Returns:
        The value returned by the coroutine on success.

    Raises:
        EndpointInvocationError: When all attempts are exhausted or a
            permanent failure is detected.
    """
    retrier = AsyncRetrying(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=min_wait, max=max_wait, jitter=min_wait),
        before_sleep=_log_before_retry(label),
        reraise=True,
    )

    async def _attempt() -> Any:
        result = await coro_factory()

        from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse

        if isinstance(result, ErrorResponse):
            raise classify_error_response(result)

        return result

    return await retrier(_attempt)
