"""Regression tests for event-loop reuse across tests in a run.

A closed event loop leaves loop-bound resources dead behind it. The SDK RPC client
is cached per thread and holds ``redis.asyncio`` connections, so running each test
on its own ``asyncio.run()`` made every second SDK test fail with
"Event loop is closed", surfaced to users as "Failed to send request to SDK".
"""

import asyncio

from rhesis.backend.jobs.execution.shared import run_on_thread_loop


class TestRunOnThreadLoop:
    def test_reuses_one_loop_across_calls(self):
        """The whole point: consecutive calls must land on the same loop."""

        async def _loop_id():
            return id(asyncio.get_running_loop())

        seen = [run_on_thread_loop(_loop_id()) for _ in range(5)]
        assert len(set(seen)) == 1, f"expected one loop, saw {len(set(seen))}"

    def test_loop_stays_open_between_calls(self):
        """asyncio.run() closes the loop on exit; this must not."""

        async def _get_loop():
            return asyncio.get_running_loop()

        loop = run_on_thread_loop(_get_loop())
        assert not loop.is_closed()

        run_on_thread_loop(_get_loop())
        assert not loop.is_closed()

    def test_resources_bound_to_the_loop_survive(self):
        """An asyncio primitive built in one call is still usable in the next.

        This is the property the cached Redis client depends on. Under
        ``asyncio.run()`` the second call raises "Event loop is closed".
        """
        holder = {}

        async def _create():
            holder["event"] = asyncio.Event()
            holder["loop"] = asyncio.get_running_loop()

        async def _reuse():
            # Touching a loop-bound object from a later call must not blow up.
            holder["event"].set()
            return holder["loop"] is asyncio.get_running_loop()

        run_on_thread_loop(_create())
        assert run_on_thread_loop(_reuse()) is True

    def test_rebuilds_after_the_loop_is_closed(self):
        """A closed loop is replaced rather than reused."""

        async def _get_loop():
            return asyncio.get_running_loop()

        first = run_on_thread_loop(_get_loop())
        first.close()

        second = run_on_thread_loop(_get_loop())
        assert second is not first
        assert not second.is_closed()

    def test_returns_the_coroutine_result(self):
        async def _answer():
            await asyncio.sleep(0)
            return 42

        assert run_on_thread_loop(_answer()) == 42

    def test_propagates_exceptions(self):
        async def _boom():
            raise ValueError("boom")

        try:
            run_on_thread_loop(_boom())
        except ValueError as e:
            assert str(e) == "boom"
        else:
            raise AssertionError("exception did not propagate")

    def test_each_thread_gets_its_own_loop(self):
        """Thread-local, so it is safe under Celery's --pool threads."""
        import threading

        async def _loop_id():
            return id(asyncio.get_running_loop())

        results = {}

        def _work(name):
            results[name] = run_on_thread_loop(_loop_id())

        threads = [threading.Thread(target=_work, args=(f"t{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results.values())) == 3, "threads must not share a loop"
