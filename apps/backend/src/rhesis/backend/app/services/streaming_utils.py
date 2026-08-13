"""Shared utilities for NDJSON streaming responses."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from rhesis.backend.app.constants import REQUIREMENT_LIST_KEY
from rhesis.sdk.synthesizers.streaming import IncrementalJsonArrayParser

logger = logging.getLogger(__name__)

__all__ = ["ndjson", "EventFanout", "IncrementalJsonArrayParser", "IncrementalConfigParser"]

_CONFIG_ARRAY_KEYS = (REQUIREMENT_LIST_KEY, "topics", "categories")

_FANOUT_DONE = object()


def ndjson(event: Dict[str, Any]) -> bytes:
    """Encode a single NDJSON event."""
    return (json.dumps(event) + "\n").encode("utf-8")


class EventFanout:
    """Fan out concurrent async work and drain result events as they complete.

    Call ``spawn()`` to register a background task; the task (or any task it
    spawns before returning) calls ``emit()`` to push a result. ``stream()``
    yields events as they arrive and returns once every spawned task has
    finished and the queue is empty — no polling: a task's done-callback
    pushes a wake-up sentinel the moment the outstanding count reaches zero.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._outstanding = 0

    def spawn(self, coro) -> "asyncio.Task":
        """Track ``coro`` as outstanding work and run it as a task."""
        self._outstanding += 1
        task = asyncio.create_task(coro)
        task.add_done_callback(self._on_done)
        return task

    def _on_done(self, task: "asyncio.Task") -> None:
        self._outstanding -= 1
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            logger.exception("EventFanout task failed")
        if self._outstanding == 0:
            self._queue.put_nowait(_FANOUT_DONE)

    async def emit(self, event: Dict[str, Any]) -> None:
        """Push a result event, to be picked up by ``stream()``/``drain_ready()``."""
        await self._queue.put(event)

    def drain_ready(self) -> List[Dict[str, Any]]:
        """Pop events already queued, without waiting.

        For interleaving with a producer loop that has its own items to
        yield between checking on background work.
        """
        ready = []
        while not self._queue.empty():
            event = self._queue.get_nowait()
            if event is not _FANOUT_DONE:
                ready.append(event)
        return ready

    async def stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield remaining events until every spawned task has finished."""
        while self._outstanding > 0 or not self._queue.empty():
            event = await self._queue.get()
            if event is _FANOUT_DONE:
                continue
            yield event


class IncrementalConfigParser:
    """Parse a streaming config response with multiple named arrays.

    Wraps ``IncrementalJsonArrayParser`` and tracks which top-level key
    (``requirements``, ``topics``, ``categories``) each object belongs to by
    detecting when the inner parser enters each successive array.

    Yields ``(category, obj)`` tuples.
    """

    def __init__(self):
        self._inner = IncrementalJsonArrayParser()
        self._current_key: Optional[str] = None
        self._next_array_index = 0

    def feed(self, chunk: str) -> List[Tuple[str, dict]]:
        results: List[Tuple[str, dict]] = []
        for char in chunk:
            was_in_array = self._inner._in_array
            objects = self._inner.feed(char)
            if not was_in_array and self._inner._in_array:
                if self._next_array_index < len(_CONFIG_ARRAY_KEYS):
                    self._current_key = _CONFIG_ARRAY_KEYS[self._next_array_index]
                    self._next_array_index += 1
                else:
                    self._current_key = "unknown"
            category = self._current_key or "unknown"
            results.extend((category, obj) for obj in objects)
        return results
