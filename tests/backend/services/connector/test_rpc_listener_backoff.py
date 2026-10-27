"""The RPC listener must pause between errors instead of spinning.

A dead Redis connection makes blpop fail instantly. With no pause, the loop
logged the same traceback thousands of times a second and filled dev log files
with tens of gigabytes.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

from rhesis.backend.app.services.connector.manager import ConnectionManager

MANAGER = "rhesis.backend.app.services.connector.manager"


def _redis(blpop_side_effect):
    redis = MagicMock()
    redis.is_available = True
    redis.client.blpop = AsyncMock(side_effect=blpop_side_effect)
    return redis


@pytest.mark.asyncio
async def test_listener_backs_off_between_errors():
    errors = [RedisError("Buffer is closed.")] * 6
    redis = _redis([*errors, asyncio.CancelledError()])

    with (
        patch(f"{MANAGER}.redis_manager", redis),
        patch(f"{MANAGER}.asyncio.sleep", new_callable=AsyncMock) as sleep,
        pytest.raises(asyncio.CancelledError),
    ):
        await ConnectionManager()._listen_for_rpc_requests()

    assert [c.args[0] for c in sleep.await_args_list] == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]


@pytest.mark.asyncio
async def test_listener_backoff_resets_after_success():
    redis = _redis(
        [RedisError("down"), RedisError("down"), None, RedisError("down"), asyncio.CancelledError()]
    )

    with (
        patch(f"{MANAGER}.redis_manager", redis),
        patch(f"{MANAGER}.asyncio.sleep", new_callable=AsyncMock) as sleep,
        pytest.raises(asyncio.CancelledError),
    ):
        await ConnectionManager()._listen_for_rpc_requests()

    assert [c.args[0] for c in sleep.await_args_list] == [1.0, 2.0, 1.0]
