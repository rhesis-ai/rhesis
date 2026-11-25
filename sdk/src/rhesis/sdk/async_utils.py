"""Async utilities for bridging sync and async code.

Provides run_sync() for executing async coroutines from synchronous contexts,
using a persistent background thread/loop to avoid event loop lifecycle issues.
"""

import asyncio
import atexit
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Thread

logger = logging.getLogger(__name__)

_background_loop = None
_background_thread = None
# Threads making their first run_sync() call at the same moment would otherwise each start
# a loop, and litellm's Vertex client then mixes state across them and hangs.
_loop_lock = threading.Lock()


def _loop_threads() -> int:
    """Threads for blocking calls made from the background loop (``asyncio.to_thread``).

    Providers without an async client and several metric fallbacks run their blocking
    call this way, one thread each for its whole duration. Python's default pool is
    ``min(32, os.cpu_count() + 4)``, and in a container ``os.cpu_count()`` reports the
    host's cores, not the container's: 14 on a 10-core host, whatever the workload. That
    capped a process at 14 model calls in flight. These threads mostly wait on the
    network, so the size follows concurrency, not cores.
    """
    return int(os.environ.get("RHESIS_SDK_LOOP_THREADS", "64"))


def reset_litellm_vertex_async_locks() -> None:
    """Clear litellm Vertex AI asyncio locks tied to a dead event loop.

    litellm.main keeps a module-level ``vertex_chat_completion`` singleton
    whose ``_async_refresh_locks`` are bound to whichever event loop first
    touched them.  After ``asyncio.run()`` closes its loop, the next call
    on a fresh loop raises "Lock ... is bound to a different event loop".
    """
    try:
        import litellm.main as litellm_main

        vertex = getattr(litellm_main, "vertex_chat_completion", None)
        if vertex is None:
            return
        vertex._async_refresh_locks.clear()
        vertex._async_refresh_lock_refcounts.clear()
        for task in vertex._background_refresh_tasks.values():
            if not task.done():
                task.cancel()
        vertex._background_refresh_tasks.clear()
    except Exception:
        logger.debug("Could not reset litellm Vertex async locks", exc_info=True)


class _PerLoopLoggingWorker:
    """Stands in for litellm's ``GLOBAL_LOGGING_WORKER`` with one worker per event loop.

    litellm queues every async call's success logging on one process-wide worker, whose queue
    and task belong to a single loop. When calls come from several loops (one per worker
    thread, or ``asyncio.run()`` per call), the worker rebinds to each new loop in turn. The
    task it leaves on the old loop is garbage collected while pending ("Task was destroyed
    but it is pending!"), and coroutines it moves across loops fail with "cannot reuse
    already awaited coroutine".
    """

    def __init__(self, worker_class, fallback):
        self._worker_class = worker_class
        self._fallback = fallback
        # Not a WeakKeyDictionary: each worker holds its loop, so the key would never die.
        self._workers = {}
        self._lock = threading.Lock()

    def _worker(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self._fallback
        with self._lock:
            worker = self._workers.get(loop)
            if worker is None:
                worker = self._workers[loop] = self._worker_class()
                self._move_closed_loops_to(worker)
            return worker

    def _move_closed_loops_to(self, worker):
        """Drop the workers of closed loops, handing their unsent logging to ``worker``.

        ``asyncio.run()`` often closes its loop before the worker has run, so its queue still
        holds that call's success logging. litellm moves it the same way on a loop change.
        """
        for loop in [loop for loop in self._workers if loop.is_closed()]:
            closed = self._workers.pop(loop)
            try:
                self._hand_over(closed, worker)
            except Exception:
                # These are litellm internals; if a release changes them, lose the leftover
                # logging rather than fail the call that is being made.
                logger.debug("Could not move litellm logging off a closed loop", exc_info=True)

    @staticmethod
    def _hand_over(closed, worker):
        # Each worker registers an atexit flush; without this they pile up.
        atexit.unregister(closed._flush_on_exit)
        leftovers = closed._unstarted_dequeued_tasks()
        if closed._queue is not None:
            leftovers += closed._drain_pending(closed._queue)
        if not leftovers:
            return
        worker.start()
        for task in leftovers:
            try:
                worker._queue.put_nowait(task)
            except asyncio.QueueFull:
                task["coroutine"].close()

    def __getattr__(self, name):
        return getattr(self._worker(), name)


def use_per_loop_litellm_logging_worker() -> None:
    """Give each event loop its own litellm logging worker. Idempotent.

    litellm's completion and caching paths look ``GLOBAL_LOGGING_WORKER`` up at call time,
    so replacing it covers every call made afterwards. Its realtime and Bedrock realtime
    handlers bind the original worker at import and keep it.
    """
    try:
        from litellm.litellm_core_utils import logging_worker
    except ImportError:
        return
    current = logging_worker.GLOBAL_LOGGING_WORKER
    if isinstance(current, _PerLoopLoggingWorker):
        return
    logging_worker.GLOBAL_LOGGING_WORKER = _PerLoopLoggingWorker(
        logging_worker.LoggingWorker, fallback=current
    )


def _get_background_loop():
    """Lazily create a single background thread with its own event loop."""
    global _background_loop, _background_thread
    with _loop_lock:
        if _background_loop is None or _background_loop.is_closed():
            if _background_loop is not None and _background_loop.is_closed():
                reset_litellm_vertex_async_locks()
            _background_loop = asyncio.new_event_loop()
            _background_loop.set_default_executor(
                ThreadPoolExecutor(max_workers=_loop_threads(), thread_name_prefix="rhesis-sdk-io")
            )
            _background_thread = Thread(
                target=_background_loop.run_forever,
                daemon=True,
            )
            _background_thread.start()
            atexit.register(close_background_loop)
        return _background_loop


def close_background_loop():
    """Stop and close the background event loop and thread. Idempotent.

    Call explicitly in long-running processes or test suites to avoid resource
    leaks. Also registered as an atexit handler when the loop is first created.
    """
    global _background_loop, _background_thread
    with _loop_lock:
        if _background_loop is None or _background_loop.is_closed():
            _background_loop = None
            _background_thread = None
            return
        try:
            atexit.unregister(close_background_loop)
            _background_loop.call_soon_threadsafe(_background_loop.stop)
            if _background_thread is not None:
                _background_thread.join(timeout=5.0)
        finally:
            try:
                _background_loop.close()
            except Exception:
                pass
            _background_loop = None
            _background_thread = None


def run_sync(coro, timeout: float | None = None):
    """Run an async coroutine from synchronous code.

    Dispatches to a persistent background thread via
    run_coroutine_threadsafe.  This avoids nested loop errors in
    Jupyter/FastAPI and prevents RuntimeError('Event loop is closed')
    from fire-and-forget cleanup tasks (e.g. litellm's AsyncHTTPHandler)
    that outlive asyncio.run().

    Args:
        coro: A coroutine object to execute.  Must be a coroutine, not an
            arbitrary awaitable -- ``run_coroutine_threadsafe`` rejects
            Tasks and Futures with ``TypeError``.
        timeout: Optional seconds to wait for the result.  ``None``
            (default) waits indefinitely.  Pass an explicit value at
            call sites where an unbounded wait would mask a hang; on
            expiry the coroutine is cancelled rather than left running.

    Returns:
        The result of the coroutine.

    Raises:
        RuntimeError: If called from the background event loop thread
            (would deadlock -- the loop cannot run the coroutine it is
            blocked on).
        concurrent.futures.TimeoutError: If *timeout* elapses first.
    """
    # Self-call on the background thread is an unbreakable deadlock: the
    # loop would block in future.result() inside its own callback and so
    # could never run the coroutine it is waiting for. Fail loudly.
    if threading.current_thread() is _background_thread:
        coro.close()  # avoid "coroutine was never awaited"
        raise RuntimeError(
            "run_sync() called from the background event loop thread. "
            "This would deadlock: the loop cannot run the coroutine it "
            "is blocked on. Await the coroutine directly instead."
        )

    # Not a deadlock, but it stalls the caller's loop for the whole call.
    # Warn so these surface before someone moves the code onto our loop.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        logger.warning(
            "run_sync() called from a thread with a running event loop; "
            "this blocks that loop until the coroutine completes. "
            "Await the coroutine directly instead.",
            stacklevel=2,
        )

    future = asyncio.run_coroutine_threadsafe(coro, _get_background_loop())
    try:
        return future.result(timeout)
    except FuturesTimeoutError as exc:
        # Reclaim the slot -- otherwise the abandoned coroutine keeps
        # running on the shared loop and burning its resources.
        future.cancel()
        # future.result() raises a bare TimeoutError whose str() is empty,
        # which downstream error formatters read as "no detail" and replace
        # with a generic message. Re-raise with the reason spelled out.
        raise FuturesTimeoutError(f"Operation timed out after {timeout}s") from exc
