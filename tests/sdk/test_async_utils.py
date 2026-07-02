"""Tests for rhesis.sdk.async_utils."""

import asyncio

import pytest

from rhesis.sdk.async_utils import (
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
        lock = asyncio.Lock()
        import litellm.main as litellm_main

        vertex = litellm_main.vertex_chat_completion
        key = ("creds", "project")
        vertex._async_refresh_locks[key] = lock
        vertex._async_refresh_lock_refcounts[key] = 1
    finally:
        loop_a.close()

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
