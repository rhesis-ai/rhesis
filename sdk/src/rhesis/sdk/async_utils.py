"""Async utilities for bridging sync and async code.

Provides run_sync() for executing async coroutines from synchronous contexts,
using a persistent background thread/loop to avoid event loop lifecycle issues.
"""

import asyncio
import atexit
import logging
import threading
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Thread

logger = logging.getLogger(__name__)

_background_loop = None
_background_thread = None


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


def _get_background_loop():
    """Lazily create a single background thread with its own event loop."""
    global _background_loop, _background_thread
    if _background_loop is None or _background_loop.is_closed():
        if _background_loop is not None and _background_loop.is_closed():
            reset_litellm_vertex_async_locks()
        _background_loop = asyncio.new_event_loop()
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
