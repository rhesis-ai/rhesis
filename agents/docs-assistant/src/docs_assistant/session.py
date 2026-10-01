"""In-memory conversation store: LRU-capped, idle TTL, one lock per conversation.

Turns on one conversation must run one at a time, or two overlapping turns read the same state
and the second write loses the first. Everything here runs on the event loop, so asyncio locks
are enough. The `Store` protocol is what a shared store (Redis) would implement later.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from docs_assistant.state import ConversationState

MAX_CONVERSATIONS = 256
IDLE_TTL_SECONDS = 1800


class Store(Protocol):
    def turn(self, conversation_id: str | None) -> AsyncIterator[ConversationState]: ...
    def list(self) -> dict[str, int]: ...
    def delete(self, conversation_id: str) -> bool: ...


class ConversationStore:
    def __init__(
        self,
        *,
        max_conversations: int = MAX_CONVERSATIONS,
        idle_ttl: float = IDLE_TTL_SECONDS,
        clock=time.monotonic,
    ) -> None:
        self.max_conversations = max_conversations
        self.idle_ttl = idle_ttl
        self._clock = clock
        self._states: OrderedDict[str, tuple[ConversationState, float]] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def turn(self, conversation_id: str | None) -> AsyncIterator[ConversationState]:
        """Hold the conversation's lock for one turn. An unknown or expired id starts fresh."""
        conversation_id = conversation_id or uuid.uuid4().hex
        lock = self._locks.setdefault(conversation_id, asyncio.Lock())
        async with lock:
            state = self._get(conversation_id) or ConversationState(conversation_id)
            try:
                yield state
            finally:
                self._put(state)

    def get(self, conversation_id: str) -> ConversationState | None:
        return self._get(conversation_id)

    def list(self) -> dict[str, int]:
        self._expire()
        return {cid: state.turn for cid, (state, _) in self._states.items()}

    def delete(self, conversation_id: str) -> bool:
        self._locks.pop(conversation_id, None)
        return self._states.pop(conversation_id, None) is not None

    def _get(self, conversation_id: str) -> ConversationState | None:
        self._expire()
        entry = self._states.get(conversation_id)
        if entry is None:
            return None
        self._states.move_to_end(conversation_id)
        return entry[0]

    def _put(self, state: ConversationState) -> None:
        self._states[state.conversation_id] = (state, self._clock())
        self._states.move_to_end(state.conversation_id)
        while len(self._states) > self.max_conversations:
            oldest, _ = self._states.popitem(last=False)
            self._drop_lock(oldest)

    def _expire(self) -> None:
        cutoff = self._clock() - self.idle_ttl
        for conversation_id in [c for c, (_, seen) in self._states.items() if seen < cutoff]:
            del self._states[conversation_id]
            self._drop_lock(conversation_id)

    def _drop_lock(self, conversation_id: str) -> None:
        # A lock someone is waiting on stays, so their turn still runs one at a time.
        lock = self._locks.get(conversation_id)
        if lock is not None and not lock.locked():
            del self._locks[conversation_id]
