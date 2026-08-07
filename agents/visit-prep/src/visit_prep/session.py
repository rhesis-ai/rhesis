"""In-memory conversation sessions for multi-turn Visit-Prep chat."""

from __future__ import annotations

import asyncio
import uuid
from threading import Lock
from typing import Any

from haystack import Pipeline

from visit_prep.pipeline import build_coordinator_pipeline, run_turn, run_turn_async
from visit_prep.state import VisitPrepState


class StateStore:
    """Thread-safe in-memory store of :class:`VisitPrepState` keyed by conversation id.

    Turns on one conversation must serialize, or two overlapping turns read the same state
    and the second write loses the first. Both a sync and an async lock are offered per
    conversation because the two entry points cannot share one: a ``threading.Lock`` held
    across an ``await`` blocks the whole event loop.
    """

    def __init__(self, *, max_conversations: int = 256) -> None:
        self._states: dict[str, VisitPrepState] = {}
        self._lock = Lock()
        self._conversation_locks: dict[str, Lock] = {}
        self._async_locks: dict[str, asyncio.Lock] = {}
        self._max_conversations = max_conversations

    def _evict_oldest_if_needed(self) -> None:
        while len(self._states) >= self._max_conversations:
            oldest_id = next(iter(self._states))
            del self._states[oldest_id]
            self._forget_locks(oldest_id)

    def _forget_locks(self, conversation_id: str) -> None:
        self._conversation_locks.pop(conversation_id, None)
        self._async_locks.pop(conversation_id, None)

    def conversation_lock(self, conversation_id: str) -> Lock:
        """Return a stable per-conversation lock for the synchronous entry point."""
        with self._lock:
            lock = self._conversation_locks.get(conversation_id)
            if lock is None:
                lock = Lock()
                self._conversation_locks[conversation_id] = lock
            return lock

    def async_conversation_lock(self, conversation_id: str) -> asyncio.Lock:
        """Return a stable per-conversation ``asyncio.Lock`` for the async entry point."""
        with self._lock:
            lock = self._async_locks.get(conversation_id)
            if lock is None:
                lock = asyncio.Lock()
                self._async_locks[conversation_id] = lock
            return lock

    def get(self, conversation_id: str) -> VisitPrepState:
        with self._lock:
            return self._states.get(conversation_id, VisitPrepState()).model_copy(deep=True)

    def set(self, conversation_id: str, state: VisitPrepState) -> None:
        with self._lock:
            if conversation_id not in self._states:
                self._evict_oldest_if_needed()
            self._states[conversation_id] = state.model_copy(deep=True)

    def list_conversations(self) -> dict[str, int]:
        with self._lock:
            return {
                conversation_id: stored.turn for conversation_id, stored in self._states.items()
            }

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id not in self._states:
                return False
            del self._states[conversation_id]
            self._forget_locks(conversation_id)
            return True


default_store = StateStore()

_default_pipeline: Pipeline | None = None
_pipeline_init_lock = Lock()


def get_default_pipeline() -> Pipeline:
    """Return the process-wide coordinator pipeline, building it once on first use.

    Concurrent turns share this one instance, which the previous design serialized behind a
    global run lock. Dropping that lock rests on all three shared objects holding no per-run
    state: ``Pipeline.run`` keeps its bookkeeping in locals, the Agent builds a fresh
    ``State`` per run and otherwise only flips idempotent warm-up flags, and
    ``GoogleGenAIChatGenerator`` assigns to ``self`` in ``__init__`` alone — its ``run``
    reads configuration and calls the client. That client is ``google-genai``'s, built on
    ``httpx.Client``, which is safe to share across threads.
    """
    global _default_pipeline
    if _default_pipeline is None:
        with _pipeline_init_lock:
            if _default_pipeline is None:
                _default_pipeline = build_coordinator_pipeline()
    return _default_pipeline


def run_chat_turn(
    message: str,
    *,
    conversation_id: str | None = None,
    store: StateStore | None = None,
    pipeline: Pipeline | None = None,
) -> dict[str, Any]:
    """Run one chat turn: load state, invoke the coordinator pipeline, persist updates."""
    active_store = store or default_store
    conv_id = conversation_id or str(uuid.uuid4())
    pipe = pipeline or get_default_pipeline()

    with active_store.conversation_lock(conv_id):
        state = active_store.get(conv_id)
        result = run_turn(message, state, pipeline=pipe)
        active_store.set(conv_id, result["state"])

    result["conversation_id"] = conv_id
    return result


async def run_chat_turn_async(
    message: str,
    *,
    conversation_id: str | None = None,
    store: StateStore | None = None,
    pipeline: Pipeline | None = None,
) -> dict[str, Any]:
    """Async variant, serialized per conversation but concurrent across conversations."""
    active_store = store or default_store
    conv_id = conversation_id or str(uuid.uuid4())
    pipe = pipeline or get_default_pipeline()

    async with active_store.async_conversation_lock(conv_id):
        state = active_store.get(conv_id)
        result = await run_turn_async(message, state, pipeline=pipe)
        active_store.set(conv_id, result["state"])

    result["conversation_id"] = conv_id
    return result


__all__ = [
    "StateStore",
    "default_store",
    "get_default_pipeline",
    "run_chat_turn",
    "run_chat_turn_async",
]
