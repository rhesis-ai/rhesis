"""Per-conversation state: the trip brief and the user-visible transcript.

In-process and bounded, which is enough for a local demo. A deployment would put this
behind a database; nothing above this module would change.
"""

from __future__ import annotations

import asyncio
import uuid
from threading import Lock
from typing import Any

from agent_framework import Message
from rhesis.telemetry.context import get_conversation_id, set_conversation_id

from travel_agent.runner import run_turn
from travel_agent.state import TripBrief


class StateStore:
    """Thread-safe store of ``(TripBrief, messages)`` per conversation.

    Bounded so a long-running demo server does not grow without limit. Briefs are handed
    out as deep copies and only written back when a turn succeeds, so a turn that raises
    part-way through cannot leave half-applied state behind.
    """

    def __init__(
        self,
        *,
        max_conversations: int = 256,
        max_messages_per_conversation: int = 200,
    ) -> None:
        self._briefs: dict[str, TripBrief] = {}
        self._messages: dict[str, list[Message]] = {}
        self._lock = Lock()
        self._async_locks: dict[str, tuple[int, asyncio.Lock]] = {}
        self._max_conversations = max_conversations
        self._max_messages = max_messages_per_conversation

    def _evict_oldest_if_needed(self) -> None:
        while len(self._briefs) >= self._max_conversations:
            oldest = next(iter(self._briefs))
            self._briefs.pop(oldest, None)
            self._messages.pop(oldest, None)
            self._async_locks.pop(oldest, None)

    def snapshot(self, conversation_id: str) -> tuple[TripBrief, list[Message]]:
        """A private copy of the conversation's brief and history."""
        with self._lock:
            brief = self._briefs.get(conversation_id)
            messages = self._messages.get(conversation_id, [])
            return (brief.model_copy(deep=True) if brief else TripBrief()), list(messages)

    def save(self, conversation_id: str, brief: TripBrief, messages: list[Message]) -> None:
        with self._lock:
            if conversation_id not in self._briefs:
                self._evict_oldest_if_needed()
            self._briefs[conversation_id] = brief
            self._messages[conversation_id] = messages[-self._max_messages :]

    def get_brief(self, conversation_id: str) -> TripBrief | None:
        with self._lock:
            brief = self._briefs.get(conversation_id)
            return brief.model_copy(deep=True) if brief else None

    def get_messages(self, conversation_id: str) -> list[Message] | None:
        with self._lock:
            stored = self._messages.get(conversation_id)
            return list(stored) if stored is not None else None

    def list_conversations(self) -> dict[str, int]:
        with self._lock:
            return {conv_id: len(messages) for conv_id, messages in self._messages.items()}

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            existed = self._briefs.pop(conversation_id, None) is not None
            self._messages.pop(conversation_id, None)
            self._async_locks.pop(conversation_id, None)
            return existed

    def turn_lock(self, conversation_id: str) -> asyncio.Lock:
        """Serialise turns within one conversation.

        Keyed by the running event loop as well as the conversation: the Rhesis connector
        runs each turn on a fresh loop, and an ``asyncio.Lock`` bound to a dead loop
        raises the moment it is contended.
        """
        loop_id = id(asyncio.get_running_loop())
        with self._lock:
            cached = self._async_locks.get(conversation_id)
            if cached is None or cached[0] != loop_id:
                cached = (loop_id, asyncio.Lock())
                self._async_locks[conversation_id] = cached
            return cached[1]


default_store = StateStore()


async def run_chat_turn(
    message: str,
    *,
    conversation_id: str | None = None,
    store: StateStore | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run one chat turn: load state, run the turn, persist the result."""
    active_store = store or default_store
    conv_id = conversation_id or str(uuid.uuid4())

    # Mark this as a real conversation turn so the MAF integration stamps the workflow's
    # root span as a Rhesis conversation turn root, keyed by this id so turns group
    # together. One-shot callers that skip this stay single-turn.
    previous_conversation_id = get_conversation_id()
    set_conversation_id(conv_id)
    try:
        async with active_store.turn_lock(conv_id):
            brief, history = active_store.snapshot(conv_id)
            result = await run_turn(
                brief,
                message,
                conversation_history=history or None,
                client=client,
            )
            active_store.save(conv_id, result["brief"], result["messages"])
    finally:
        set_conversation_id(previous_conversation_id)

    result["conversation_id"] = conv_id
    return result


def run_chat_turn_sync(
    message: str,
    *,
    conversation_id: str | None = None,
    store: StateStore | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Sync wrapper for callers without a running event loop (e.g. connector handlers)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_chat_turn(
                message,
                conversation_id=conversation_id,
                store=store,
                client=client,
            )
        )
    raise RuntimeError(
        "run_chat_turn_sync cannot be called from an active event loop; use run_chat_turn instead."
    )


__all__ = [
    "StateStore",
    "default_store",
    "run_chat_turn",
    "run_chat_turn_sync",
]
