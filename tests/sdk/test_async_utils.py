"""Tests for rhesis.sdk.async_utils."""

import asyncio
import threading
from concurrent.futures import TimeoutError as FuturesTimeoutError

import pytest

from rhesis.sdk.async_utils import (
    _get_background_loop,
    close_background_loop,
    reset_litellm_vertex_async_locks,
    run_sync,
)


def test_close_background_loop_idempotent():
    """close_background_loop is idempotent when loop was never created."""
    close_background_loop()
    close_background_loop()


@pytest.mark.asyncio
async def test_close_background_loop_after_run_sync():
    """close_background_loop cleans up after run_sync creates the background loop.

    run_sync uses the background loop when called from an async context (where
    get_running_loop() succeeds). This test triggers that path.
    """

    async def dummy():
        return "ok"

    # From async context, run_sync uses background loop
    result = run_sync(dummy())
    assert result == "ok"

    close_background_loop()

    # Can still use run_sync after close (creates a new loop)
    result2 = run_sync(dummy())
    assert result2 == "ok"

    close_background_loop()


def test_reset_litellm_vertex_async_locks_clears_stale_locks():
    """Locks created on a closed loop must be cleared before the next use."""
    loop_a = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop_a)
        lock = asyncio.Lock()
        import litellm.main as litellm_main

        vertex = litellm_main.vertex_chat_completion
        key = ("creds", "project")
        vertex._async_refresh_locks[key] = lock
        vertex._async_refresh_lock_refcounts[key] = 1
    finally:
        loop_a.close()
        asyncio.set_event_loop(None)

    reset_litellm_vertex_async_locks()

    import litellm.main as litellm_main

    vertex = litellm_main.vertex_chat_completion
    assert vertex._async_refresh_locks == {}
    assert vertex._async_refresh_lock_refcounts == {}


def test_run_sync_reuses_background_loop_across_calls():
    """Celery-style repeated sync entry points must share one loop."""
    loop_ids: list[int] = []

    async def record_loop():
        loop_ids.append(id(asyncio.get_running_loop()))
        return "ok"

    close_background_loop()
    run_sync(record_loop())
    run_sync(record_loop())
    assert len(loop_ids) == 2
    assert loop_ids[0] == loop_ids[1]
    close_background_loop()


# ---------------------------------------------------------------------------
# run_sync self-call guard (Fix 2)
# ---------------------------------------------------------------------------


def test_run_sync_raises_on_self_call():
    """Calling run_sync from the background loop thread raises RuntimeError."""
    close_background_loop()

    error_holder = []

    async def call_run_sync_from_loop():
        async def inner():
            return 42

        try:
            run_sync(inner())
        except RuntimeError as exc:
            error_holder.append(exc)

    loop = _get_background_loop()
    future = asyncio.run_coroutine_threadsafe(call_run_sync_from_loop(), loop)
    future.result(timeout=5)

    assert len(error_holder) == 1
    assert "deadlock" in str(error_holder[0]).lower()
    close_background_loop()


def test_run_sync_closes_coroutine_on_self_call():
    """The coroutine is closed (no 'never awaited' warning) on self-call."""
    close_background_loop()
    import warnings

    async def inner():
        return 42

    async def trigger():
        coro = inner()
        try:
            run_sync(coro)
        except RuntimeError:
            pass
        # After the RuntimeError, coro should be closed -- calling
        # close() again is a no-op and should not raise.
        coro.close()

    loop = _get_background_loop()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        future = asyncio.run_coroutine_threadsafe(trigger(), loop)
        future.result(timeout=5)

    never_awaited = [x for x in w if "never awaited" in str(x.message)]
    assert never_awaited == []
    close_background_loop()


# ---------------------------------------------------------------------------
# run_sync timeout (Fix 2)
# ---------------------------------------------------------------------------


def test_run_sync_timeout_raises():
    """A slow coroutine with timeout raises TimeoutError."""
    close_background_loop()

    async def slow():
        await asyncio.sleep(60)

    with pytest.raises(FuturesTimeoutError):
        run_sync(slow(), timeout=0.1)

    close_background_loop()


def test_run_sync_timeout_cancels_coroutine():
    """A timed-out coroutine is cancelled, not left running on the loop."""
    close_background_loop()

    cancelled = threading.Event()

    async def slow():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with pytest.raises(FuturesTimeoutError):
        run_sync(slow(), timeout=0.1)

    assert cancelled.wait(timeout=5), "coroutine was not cancelled after timeout"
    close_background_loop()


# ---------------------------------------------------------------------------
# generate_stream deadlock regression (Fix 1)
# ---------------------------------------------------------------------------


def test_generate_stream_does_not_deadlock():
    """BaseLLM.generate_stream must not call run_sync on the background loop.

    Before Fix 1, a BaseLLM subclass that only implemented a_generate
    would deadlock when generate_stream was called from an async context
    on the background loop thread (the architect's execution path).
    """
    close_background_loop()

    from rhesis.sdk.models.base import BaseLLM

    class StubLLM(BaseLLM):
        def load_model(self, *args, **kwargs):
            pass

        async def a_generate(self, *args, **kwargs):
            return "hello from a_generate"

        def generate_batch(self, *args, **kwargs):
            return []

    llm = StubLLM(model_name="stub")

    async def collect_stream():
        chunks = []
        async for chunk in llm.generate_stream(prompt="test"):
            chunks.append(chunk)
        return chunks

    # Run on the background loop thread -- this is the exact path
    # the architect worker takes.
    loop = _get_background_loop()
    future = asyncio.run_coroutine_threadsafe(collect_stream(), loop)
    result = future.result(timeout=5)

    assert result == ["hello from a_generate"]
    close_background_loop()
