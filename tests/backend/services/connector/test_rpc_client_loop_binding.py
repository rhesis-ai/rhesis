"""Regression tests for get_rpc_client()'s event-loop validation.

``redis.asyncio`` clients are bound to the loop that created them. The client is
cached per thread, but a thread is not guaranteed to keep one loop for its life:
a caller using ``asyncio.run()`` per call hands it a new loop every time. Reusing
a client across a closed loop makes every command fail with "Event loop is
closed", which reached users as "Failed to send request to SDK".
"""

import asyncio
from unittest.mock import AsyncMock, patch

from rhesis.backend.app.services.connector import rpc_client as rpc_mod


async def _fake_initialize(self):
    """Stand in for a real Redis connect, recording nothing loop-bound."""
    self._redis = AsyncMock()


class TestGetRpcClientLoopBinding:
    def setup_method(self):
        rpc_mod._tls.rpc_client = None

    def teardown_method(self):
        rpc_mod._tls.rpc_client = None

    def test_reuses_client_on_the_same_loop(self):
        """The cache must still work, or every test pays a reconnect + PING."""
        with patch.object(rpc_mod.SDKRpcClient, "initialize", _fake_initialize):

            async def _twice():
                return await rpc_mod.get_rpc_client(), await rpc_mod.get_rpc_client()

            first, second = asyncio.run(_twice())
            assert first is second

    def test_rebuilds_when_the_loop_changed(self):
        """A new loop must not inherit the previous loop's client."""
        with patch.object(rpc_mod.SDKRpcClient, "initialize", _fake_initialize):
            first = asyncio.run(rpc_mod.get_rpc_client())
            second = asyncio.run(rpc_mod.get_rpc_client())

        assert first is not second, "stale-loop client was reused"

    def test_records_the_loop_it_was_built_on(self):
        with patch.object(rpc_mod.SDKRpcClient, "initialize", _fake_initialize):

            async def _build():
                client = await rpc_mod.get_rpc_client()
                return client, asyncio.get_running_loop()

            client, loop = asyncio.run(_build())

        assert client._loop is loop

    def test_rebuilds_when_redis_is_none(self):
        """Pre-existing behaviour: a torn-down client is replaced."""
        with patch.object(rpc_mod.SDKRpcClient, "initialize", _fake_initialize):

            async def _flow():
                first = await rpc_mod.get_rpc_client()
                first._redis = None
                second = await rpc_mod.get_rpc_client()
                return first, second

            first, second = asyncio.run(_flow())

        assert first is not second

    def test_alternating_calls_never_reuse_a_dead_loop(self):
        """The production signature: every other call failed, this asserts it cannot."""
        with patch.object(rpc_mod.SDKRpcClient, "initialize", _fake_initialize):
            clients = [asyncio.run(rpc_mod.get_rpc_client()) for _ in range(6)]

        # Each call ran on its own loop, so each must have produced its own client.
        assert len({id(c) for c in clients}) == 6

    def test_concurrent_first_use_builds_one_client(self):
        """Batch start: N coroutines hit a cold cache at once.

        The check and the store straddle an `await client.initialize()`, so
        without a lock every coroutine builds its own client and opens its own
        Redis connection; all but the last are orphaned and never closed.
        Measured 14 leaked connections at batch_concurrency=15.
        """
        built = []

        async def _counting_initialize(self):
            built.append(self)
            await asyncio.sleep(0.01)  # widen the window the race needs
            self._redis = AsyncMock()

        with patch.object(rpc_mod.SDKRpcClient, "initialize", _counting_initialize):

            async def _batch_start():
                return await asyncio.gather(*(rpc_mod.get_rpc_client() for _ in range(15)))

            clients = asyncio.run(_batch_start())

        assert len(built) == 1, f"built {len(built)} clients, leaking {len(built) - 1}"
        assert len({id(c) for c in clients}) == 1, "callers got different clients"

    def test_close_clears_the_recorded_loop(self):
        with patch.object(rpc_mod.SDKRpcClient, "initialize", _fake_initialize):

            async def _flow():
                client = await rpc_mod.get_rpc_client()
                await client.close()
                return client

            client = asyncio.run(_flow())

        assert client._loop is None
        assert client._redis is None
        assert getattr(rpc_mod._tls, "rpc_client", None) is None
