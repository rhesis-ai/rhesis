"""Tests for rhesis.sdk.async_utils."""

import asyncio
import gc
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
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


def test_concurrent_first_calls_share_one_loop(monkeypatch):
    """Threads making their first run_sync() call together must not each start a loop."""
    import rhesis.sdk.async_utils as async_utils

    created = []
    real_new_event_loop = asyncio.new_event_loop

    def slow_new_event_loop():
        # Widen the window between the None check and the assignment.
        threading.Event().wait(0.05)
        loop = real_new_event_loop()
        created.append(loop)
        return loop

    monkeypatch.setattr(async_utils.asyncio, "new_event_loop", slow_new_event_loop)

    async def loop_id():
        return id(asyncio.get_running_loop())

    close_background_loop()
    barrier = threading.Barrier(8)
    ids = []

    def call():
        barrier.wait()
        ids.append(run_sync(loop_id(), timeout=10))

    threads = [threading.Thread(target=call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    close_background_loop()

    assert len(created) == 1
    assert len(set(ids)) == 1


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


def test_run_sync_timeout_message_is_not_empty():
    """The timeout carries a reason.

    ``future.result()`` raises a bare TimeoutError with an empty str(),
    which error formatters read as "no detail" and swap for a generic
    message -- telling the user to check model settings on a timeout.
    """
    close_background_loop()

    async def slow():
        await asyncio.sleep(60)

    with pytest.raises(FuturesTimeoutError) as excinfo:
        run_sync(slow(), timeout=0.1)

    message = str(excinfo.value)
    assert message.strip(), "timeout must carry a message, not an empty string"
    assert "timed out" in message.lower()
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


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


@pytest.fixture
def litellm_warnings():
    """Collect warnings from asyncio and litellm, which logs to its own non-propagating logger."""
    handler = _Records()
    loggers = [logging.getLogger("asyncio"), logging.getLogger("LiteLLM")]
    for logger in loggers:
        logger.addHandler(handler)
    yield handler.messages
    for logger in loggers:
        logger.removeHandler(handler)


def test_litellm_calls_from_several_loops_leave_no_logging_errors(litellm_warnings):
    """Like the worker's run_on_thread_loop: each thread runs calls on its own lasting loop."""
    import litellm

    from rhesis.sdk.models.providers import litellm as _provider  # noqa: F401  installs the worker

    local = threading.local()

    def on_thread_loop(index):
        if getattr(local, "loop", None) is None:
            local.loop = asyncio.new_event_loop()
        return local.loop.run_until_complete(call(index))

    async def call(index):
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": str(index)}],
            mock_response="ok",
        )
        await asyncio.sleep(0.01)  # lets the logging worker pick the call up
        return response.choices[0].message.content

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(on_thread_loop, range(80)))
    gc.collect()

    assert results == ["ok"] * 80
    # The destroyed-task message names LoggingWorker._worker_loop; other tests' leftovers don't.
    assert [m for m in litellm_warnings if "LoggingWorker" in m] == []


def test_success_logging_survives_asyncio_run_per_call(monkeypatch):
    """asyncio.run() closes its loop before the worker runs; the next loop sends its logging."""
    import litellm
    from litellm.integrations.custom_logger import CustomLogger

    from rhesis.sdk.models.providers import litellm as _provider  # noqa: F401  installs the worker

    logged = []

    class Counter(CustomLogger):
        async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
            logged.append(response_obj)

    monkeypatch.setattr(litellm, "callbacks", [Counter()])

    async def call():
        return await litellm.acompletion(
            model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}], mock_response="ok"
        )

    async def call_and_wait():
        await call()
        for _ in range(100):  # until the carried-over logging has run
            if len(logged) == 11:
                break
            await asyncio.sleep(0.01)

    for _ in range(10):
        asyncio.run(call())
    asyncio.run(call_and_wait())

    assert len(logged) == 11


def test_per_loop_logging_worker_drops_closed_loops(monkeypatch):
    """asyncio.run() per call must not leave a worker, its loop and an atexit hook behind."""
    from litellm.litellm_core_utils import logging_worker

    import rhesis.sdk.async_utils as async_utils

    unregistered = []
    monkeypatch.setattr(async_utils.atexit, "unregister", unregistered.append)
    per_loop = async_utils._PerLoopLoggingWorker(logging_worker.LoggingWorker, fallback=None)

    async def touch():
        return per_loop._worker()

    first = asyncio.run(touch())
    second = asyncio.run(touch())

    assert first is not second
    assert list(per_loop._workers.values()) == [second]
    assert unregistered == [first._flush_on_exit]


def test_use_per_loop_litellm_logging_worker_is_idempotent(monkeypatch):
    from litellm.litellm_core_utils import logging_worker

    import rhesis.sdk.async_utils as async_utils

    monkeypatch.setattr(logging_worker, "GLOBAL_LOGGING_WORKER", logging_worker.LoggingWorker())
    async_utils.use_per_loop_litellm_logging_worker()
    installed = logging_worker.GLOBAL_LOGGING_WORKER
    async_utils.use_per_loop_litellm_logging_worker()

    assert isinstance(installed, async_utils._PerLoopLoggingWorker)
    assert logging_worker.GLOBAL_LOGGING_WORKER is installed


def test_a_changed_litellm_worker_does_not_break_calls(monkeypatch):
    """If litellm's worker internals change, dropping a closed loop's worker must not raise."""
    from litellm.litellm_core_utils import logging_worker

    import rhesis.sdk.async_utils as async_utils

    class ChangedWorker(logging_worker.LoggingWorker):
        def _unstarted_dequeued_tasks(self):
            raise AttributeError("renamed in a newer litellm")

    per_loop = async_utils._PerLoopLoggingWorker(ChangedWorker, fallback=None)

    async def touch():
        return per_loop._worker()

    asyncio.run(touch())
    assert isinstance(asyncio.run(touch()), ChangedWorker)
    assert len(per_loop._workers) == 1
