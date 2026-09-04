"""Regression tests: RPC-path results must not accumulate in the backend.

A Celery worker waits for its result over Redis pub/sub, never on this process's
dict. Retaining the payload after publishing leaked it for the life of the
process, because ``cleanup_test_result`` is only ever reached from the local
WebSocket path. Over a few large parallel runs that is hundreds of MB, and the
OOM kill drops every SDK WebSocket at once.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from rhesis.backend.app.services.connector.manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


class TestHeartbeatJitter:
    """One heartbeat loop runs per connected SDK, so they must not stay in lockstep.

    With tens of endpoints, loops that started together tick together forever and
    each tick fires a synchronised setex burst that saturates the Redis pool,
    queueing test-result publishing behind it.
    """

    def test_jitter_never_exceeds_the_key_ttl(self):
        """Jitter must only shorten the wait: keys carry a 30s TTL."""
        from rhesis.backend.app.services.connector.manager import (
            _HEARTBEAT_INTERVAL,
            _HEARTBEAT_JITTER,
        )

        longest = _HEARTBEAT_INTERVAL * 1.0  # jitter is uniform(1 - j, 1)
        assert longest <= _HEARTBEAT_INTERVAL
        assert _HEARTBEAT_INTERVAL < 30, "must refresh well inside the 30s key TTL"
        assert 0 < _HEARTBEAT_JITTER < 1

    def test_sleeps_are_spread_across_connections(self):
        """Consecutive waits must differ, or the loops never de-synchronise."""
        import random as _random

        from rhesis.backend.app.services.connector.manager import (
            _HEARTBEAT_INTERVAL,
            _HEARTBEAT_JITTER,
        )

        waits = {_HEARTBEAT_INTERVAL * _random.uniform(1 - _HEARTBEAT_JITTER, 1) for _ in range(50)}
        assert len(waits) > 40, "waits are not being spread"
        assert all(0 < w <= _HEARTBEAT_INTERVAL for w in waits)


class TestRpcResultCleanup:
    def test_result_is_discarded_after_publishing(self, manager):
        """No local waiter means nothing will ever read it back."""

        async def _flow():
            with patch("rhesis.backend.app.services.connector.manager.redis_manager") as rm:
                rm.is_available = True
                rm.client = AsyncMock()
                manager._resolve_test_result("invoke_abc", {"status": "success"})
                await asyncio.gather(*[t for t in manager._background_tasks])

        asyncio.run(_flow())
        assert "invoke_abc" not in manager._test_results

    def test_result_is_discarded_even_if_publish_fails(self, manager):
        """A result nobody can read is not worth retaining."""

        async def _flow():
            with patch("rhesis.backend.app.services.connector.manager.redis_manager") as rm:
                rm.is_available = True
                rm.client = AsyncMock()
                rm.client.publish.side_effect = ConnectionError("Too many connections")
                manager._resolve_test_result("invoke_boom", {"status": "success"})
                await asyncio.gather(*[t for t in manager._background_tasks])

        asyncio.run(_flow())
        assert "invoke_boom" not in manager._test_results

    def test_local_waiter_still_gets_its_result(self, manager):
        """The local WebSocket path reads the dict after the event fires.

        That path must keep working: it cleans up via cleanup_test_result.
        """

        async def _flow():
            event = asyncio.Event()
            manager._result_events["invoke_local"] = event
            with patch("rhesis.backend.app.services.connector.manager.redis_manager") as rm:
                rm.is_available = True
                rm.client = AsyncMock()
                manager._resolve_test_result("invoke_local", {"status": "success"})
                await asyncio.gather(*[t for t in manager._background_tasks])
            return event

        event = asyncio.run(_flow())
        assert event.is_set()
        assert manager._test_results.get("invoke_local") == {"status": "success"}

    def test_metric_result_is_discarded_after_publishing(self, manager):
        async def _flow():
            with patch("rhesis.backend.app.services.connector.manager.redis_manager") as rm:
                rm.is_available = True
                rm.client = AsyncMock()
                manager._resolve_metric_result("metric_1", {"status": "success"})
                await asyncio.gather(*[t for t in manager._background_tasks])

        asyncio.run(_flow())
        assert "metric_1" not in manager._metric_results

    def test_many_rpc_results_do_not_accumulate(self, manager):
        """The shape of the leak: a batch run must not grow the dict."""

        async def _flow():
            with patch("rhesis.backend.app.services.connector.manager.redis_manager") as rm:
                rm.is_available = True
                rm.client = AsyncMock()
                for i in range(200):
                    manager._resolve_test_result(f"invoke_{i}", {"status": "success"})
                await asyncio.gather(*[t for t in manager._background_tasks])

        asyncio.run(_flow())
        assert manager._test_results == {}
