"""Unit tests for EventFanout, the fan-out/fan-in helper behind the NDJSON streams."""

import asyncio
import logging

import pytest

from rhesis.backend.app.services.streaming_utils import EventFanout


async def _collect(fanout: EventFanout) -> list:
    return [event async for event in fanout.stream()]


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventFanout:
    """EventFanout fans out spawned tasks and drains their emitted events."""

    async def test_stream_yields_events_from_all_spawned_tasks(self):
        fanout = EventFanout()

        async def worker(n: int):
            await asyncio.sleep(0.01 * (3 - n))
            await fanout.emit({"n": n})

        for n in range(3):
            fanout.spawn(worker(n))

        events = await asyncio.wait_for(_collect(fanout), timeout=2)

        assert {e["n"] for e in events} == {0, 1, 2}

    async def test_stream_terminates_with_no_spawned_tasks(self):
        fanout = EventFanout()

        events = await asyncio.wait_for(_collect(fanout), timeout=2)

        assert events == []

    async def test_dynamic_spawn_from_within_a_task_is_not_dropped(self):
        """A task spawning another task before it returns must not let stream()
        finish early — the classic case is _invoke_one spawning _evaluate_one."""
        fanout = EventFanout()

        async def child():
            await fanout.emit({"who": "child"})

        async def parent():
            fanout.spawn(child())
            await fanout.emit({"who": "parent"})

        fanout.spawn(parent())

        events = await asyncio.wait_for(_collect(fanout), timeout=2)

        assert {e["who"] for e in events} == {"parent", "child"}

    async def test_task_exception_is_logged_and_does_not_hang_stream(self, caplog):
        fanout = EventFanout()

        async def bad():
            raise RuntimeError("boom")

        async def good():
            await fanout.emit({"ok": True})

        fanout.spawn(bad())
        fanout.spawn(good())

        with caplog.at_level(logging.ERROR):
            events = await asyncio.wait_for(_collect(fanout), timeout=2)

        assert events == [{"ok": True}]
        assert "boom" in caplog.text

    async def test_drain_ready_returns_only_already_queued_events(self):
        fanout = EventFanout()

        await fanout.emit({"idx": 0})
        await fanout.emit({"idx": 1})

        ready = fanout.drain_ready()

        assert ready == [{"idx": 0}, {"idx": 1}]
        assert fanout.drain_ready() == []

    async def test_drain_ready_does_not_yield_the_done_sentinel(self):
        fanout = EventFanout()

        async def worker():
            await fanout.emit({"done": False})

        fanout.spawn(worker())
        await asyncio.sleep(0.05)  # let the task finish and push its wake-up sentinel

        ready = fanout.drain_ready()

        assert ready == [{"done": False}]
