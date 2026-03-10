"""Async utilities for bridging sync and async code.

Provides run_sync() for executing async coroutines from synchronous contexts,
with automatic detection of running event loops (Jupyter, FastAPI, etc.).
"""

import asyncio
import atexit
from threading import Thread

_background_loop = None
_background_thread = None


def _get_background_loop():
    """Lazily create a single background thread with its own event loop."""
    global _background_loop, _background_thread
    if _background_loop is None or _background_loop.is_closed():
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


def run_sync(coro):
    """Run an async coroutine from synchronous code.

    Auto-detects the calling context:
    - No running loop (plain script): uses asyncio.run() directly
    - Running loop (Jupyter, FastAPI): dispatches to a background thread
      via run_coroutine_threadsafe to avoid nested loop errors

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine.
    """
    try:
        asyncio.get_running_loop()
        future = asyncio.run_coroutine_threadsafe(coro, _get_background_loop())
        return future.result()
    except RuntimeError:
        return asyncio.run(coro)
