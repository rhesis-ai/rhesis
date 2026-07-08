"""In-memory conversation sessions for multi-turn Dr-Rhesis chat."""

from __future__ import annotations

import uuid
from threading import Lock
from typing import Any

from dr_rhesis.pipeline import TurnComponents, build_intent_pipeline, build_turn_components, run_turn
from dr_rhesis.state import DrRhesisState


class StateStore:
    """Thread-safe in-memory store of :class:`DrRhesisState` keyed by conversation id."""

    def __init__(self, *, max_conversations: int = 256) -> None:
        self._states: dict[str, DrRhesisState] = {}
        self._lock = Lock()
        self._max_conversations = max_conversations

    def _evict_oldest_if_needed(self) -> None:
        while len(self._states) >= self._max_conversations:
            oldest_id = next(iter(self._states))
            del self._states[oldest_id]

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
            return True


default_store = StateStore()


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
    state = active_store.get(conv_id)

    # Future: set_conversation_id(conv_id) when Haystack SDK integration lands.
    pipeline = build_intent_pipeline(components or build_turn_components())
    result = run_turn(message, state, pipeline=pipeline, components=components)
    active_store.set(conv_id, result["state"])
    result["conversation_id"] = conv_id
    return result


__all__ = [
    "StateStore",
    "default_store",
    "run_chat_turn",
]
