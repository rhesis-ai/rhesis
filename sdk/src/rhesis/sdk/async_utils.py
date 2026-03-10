"""Async utilities for bridging sync and async code.

Provides run_sync() for executing async coroutines from synchronous contexts,
with automatic detection of running event loops (Jupyter, FastAPI, etc.).
"""

import asyncio
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
    return _background_loop


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
