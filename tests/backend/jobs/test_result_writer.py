"""The batch's result writer: one session for the tests it saves, each saved on its own."""

import asyncio
import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.writer import ResultWriter

_SESSION = "rhesis.backend.app.database.get_db_with_tenant_variables"
_PERSIST = "rhesis.backend.jobs.execution.batch.persist.persist_result"


def _ctx():
    ctx = MagicMock()
    ctx.organization_id, ctx.user_id, ctx.project_id = "org", "user", "project"
    return ctx


@contextmanager
def _sessions(opened):
    @contextmanager
    def session(*_args):
        db = object()
        opened.append(db)
        yield db

    with patch(_SESSION, side_effect=session):
        yield


async def _until(condition):
    # Yields to the loop until condition holds; no wall-clock waits.
    while not condition():
        await asyncio.sleep(0)


async def _wait_event(event: threading.Event):
    await asyncio.get_running_loop().run_in_executor(None, event.wait, 5)


@pytest.mark.unit
class TestResultWriter:
    def test_tests_queued_together_share_one_session(self):
        opened, saved = [], []
        started, gate = threading.Event(), threading.Event()

        def persist(ctx, test_id, *rest, db):
            started.set()
            gate.wait(5)
            saved.append((test_id, db))

        async def run():
            writer = ResultWriter(_ctx())
            # The first save holds the thread, so the rest queue up and go as one group.
            first = asyncio.ensure_future(writer.save("t0"))
            await _wait_event(started)
            rest = [asyncio.ensure_future(writer.save(f"t{i}")) for i in range(1, 5)]
            await _until(lambda: writer._queue.qsize() == 4)
            gate.set()
            await asyncio.gather(first, *rest)
            await writer.close()

        with _sessions(opened), patch(_PERSIST, side_effect=persist):
            asyncio.run(run())

        assert [t for t, _ in saved] == ["t0", "t1", "t2", "t3", "t4"]
        assert len(opened) == 2
        assert {db for _, db in saved[1:]} == {opened[1]}

    def test_a_test_is_released_once_its_own_row_commits(self):
        holding, hold_gate = threading.Event(), threading.Event()
        second_started, gate = threading.Event(), threading.Event()

        def persist(ctx, test_id, *rest, db):
            if test_id == "hold":
                holding.set()
                hold_gate.wait(5)
            if test_id == "t1":
                second_started.set()
                gate.wait(5)

        async def run():
            writer = ResultWriter(_ctx())
            blocker = asyncio.ensure_future(writer.save("hold"))
            await _wait_event(holding)
            first = asyncio.ensure_future(writer.save("t0"))
            second = asyncio.ensure_future(writer.save("t1"))
            await _until(lambda: writer._queue.qsize() == 2)
            hold_gate.set()
            await _wait_event(second_started)
            # t0 and t1 were saved as one group; t0 is free while t1 is still saving.
            await asyncio.wait_for(first, 5)
            assert not second.done()
            gate.set()
            await asyncio.gather(blocker, second)
            await writer.close()

        with _sessions([]), patch(_PERSIST, side_effect=persist):
            asyncio.run(run())

    def test_a_failed_save_fails_only_its_test(self):
        def persist(ctx, test_id, *rest, db):
            if test_id == "bad":
                raise RuntimeError("constraint")

        async def run():
            writer = ResultWriter(_ctx())
            outcomes = await asyncio.gather(
                writer.save("good"),
                writer.save("bad"),
                writer.save("also-good"),
                return_exceptions=True,
            )
            await writer.close()
            return outcomes

        with _sessions([]), patch(_PERSIST, side_effect=persist):
            good, bad, also_good = asyncio.run(run())

        assert good is None and also_good is None
        assert isinstance(bad, RuntimeError)

    def test_a_session_that_cannot_open_fails_the_group(self):
        @contextmanager
        def broken(*_args):
            raise ConnectionError("pool exhausted")
            yield

        async def run():
            writer = ResultWriter(_ctx())
            outcome = await asyncio.gather(writer.save("t1"), return_exceptions=True)
            await writer.close()
            return outcome[0]

        with patch(_SESSION, side_effect=broken), patch(_PERSIST):
            assert isinstance(asyncio.run(run()), ConnectionError)

    def test_a_cancelled_caller_still_gets_its_test_saved(self):
        saved = []
        started, gate = threading.Event(), threading.Event()

        def persist(ctx, test_id, *rest, db):
            started.set()
            gate.wait(5)
            saved.append(test_id)

        async def run():
            writer = ResultWriter(_ctx())
            task = asyncio.ensure_future(writer.save("t1"))
            await _wait_event(started)
            task.cancel()
            gate.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            await writer.close()

        with _sessions([]), patch(_PERSIST, side_effect=persist):
            asyncio.run(run())

        assert saved == ["t1"]

    def test_close_saves_what_is_queued(self):
        saved = []

        def persist(ctx, test_id, *rest, db):
            saved.append(test_id)

        async def run():
            writer = ResultWriter(_ctx())
            pending = [asyncio.ensure_future(writer.save(f"t{i}")) for i in range(3)]
            await _until(lambda: writer._queue.qsize() + len(saved) >= 3)
            await writer.close()
            await asyncio.gather(*pending)

        with _sessions([]), patch(_PERSIST, side_effect=persist):
            asyncio.run(run())

        assert saved == ["t0", "t1", "t2"]
