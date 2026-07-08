"""In-memory conversation sessions for multi-turn Dr-Rhesis chat."""

from __future__ import annotations

import uuid
from threading import Lock
from typing import Any

from haystack import Pipeline

from dr_rhesis.pipeline import TurnComponents, build_intent_pipeline, run_turn
from dr_rhesis.state import DrRhesisState


class StateStore:
    """Thread-safe in-memory store of :class:`DrRhesisState` keyed by conversation id."""

    def __init__(self, *, max_conversations: int = 256) -> None:
        self._states: dict[str, DrRhesisState] = {}
        self._lock = Lock()
        # One lock per conversation, so a request can hold the read-modify-write
        # critical section for its conversation while other conversations proceed
        # concurrently. Bounded alongside ``_states`` via the same eviction.
        self._conversation_locks: dict[str, Lock] = {}
        self._max_conversations = max_conversations

    def _evict_oldest_if_needed(self) -> None:
        while len(self._states) >= self._max_conversations:
            oldest_id = next(iter(self._states))
            del self._states[oldest_id]
            self._conversation_locks.pop(oldest_id, None)

    def conversation_lock(self, conversation_id: str) -> Lock:
        """Return a stable per-conversation lock, creating it on first use."""
        with self._lock:
            lock = self._conversation_locks.get(conversation_id)
            if lock is None:
                lock = Lock()
                self._conversation_locks[conversation_id] = lock
            return lock

    def get(self, conversation_id: str) -> DrRhesisState:
        with self._lock:
            return self._states.get(conversation_id, DrRhesisState()).model_copy(deep=True)

    def set(self, conversation_id: str, state: DrRhesisState) -> None:
        with self._lock:
            if conversation_id not in self._states:
                self._evict_oldest_if_needed()
            self._states[conversation_id] = state.model_copy(deep=True)

    def list_conversations(self) -> dict[str, int]:
        with self._lock:
            return {
                conversation_id: stored.turn
                for conversation_id, stored in self._states.items()
            }

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id not in self._states:
                return False
            del self._states[conversation_id]
            self._conversation_locks.pop(conversation_id, None)
            return True


default_store = StateStore()

# The per-turn pipeline and its shared Gemini generator are expensive to build
# (the generator initialises an API client), so build them once and reuse across
# turns instead of rebuilding on every request. Haystack does not document
# ``Pipeline.run()`` or ``GoogleGenAIChatGenerator.run()`` as safe for concurrent
# use on the same instance, and FastAPI runs our sync handler on a thread pool, so
# concurrent requests in one worker could otherwise overlap on the shared objects.
# Custom components are stateless (they deep-copy state), but we still serialize
# turns on the cached pipeline with ``_pipeline_run_lock`` as a conservative guard.
_default_pipeline: Pipeline | None = None
_pipeline_init_lock = Lock()
_pipeline_run_lock = Lock()


def get_default_pipeline() -> Pipeline:
    """Return the process-wide per-turn pipeline, building it once on first use."""
    global _default_pipeline
    if _default_pipeline is None:
        with _pipeline_init_lock:
            if _default_pipeline is None:
                _default_pipeline = build_intent_pipeline()
    return _default_pipeline


def run_chat_turn(
    message: str,
    *,
    conversation_id: str | None = None,
    store: StateStore | None = None,
    components: TurnComponents | None = None,
) -> dict[str, Any]:
    """Run one chat turn: load state, invoke the pipeline, persist updates."""
    active_store = store or default_store
    conv_id = conversation_id or str(uuid.uuid4())

    # Hold the per-conversation lock across the whole read-modify-write so two
    # concurrent requests on the same conversation_id cannot both read the same
    # prior state and clobber each other's write (lost update). Different
    # conversations use different locks and stay concurrent. The inner
    # ``_pipeline_run_lock`` still serializes runs on the shared pipeline, which
    # Haystack does not guarantee is safe for concurrent use. Lock ordering is
    # always conversation lock -> pipeline lock, so there is no deadlock.
    with active_store.conversation_lock(conv_id):
        state = active_store.get(conv_id)

        # Future: set_conversation_id(conv_id) when Haystack SDK integration lands.
        # Reuse the cached pipeline unless the caller supplies explicit components
        # (e.g. tests injecting a mock generator), which need their own pipeline.
        if components is not None:
            pipeline = build_intent_pipeline(components)
            result = run_turn(message, state, pipeline=pipeline, components=components)
        else:
            pipeline = get_default_pipeline()
            with _pipeline_run_lock:
                result = run_turn(message, state, pipeline=pipeline, components=components)
        active_store.set(conv_id, result["state"])

    result["conversation_id"] = conv_id
    return result


__all__ = [
    "StateStore",
    "default_store",
    "get_default_pipeline",
    "run_chat_turn",
]
