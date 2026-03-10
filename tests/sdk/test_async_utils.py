"""Tests for rhesis.sdk.async_utils."""

import pytest

from rhesis.sdk.async_utils import close_background_loop, run_sync


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
