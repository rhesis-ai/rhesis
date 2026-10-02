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
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Protocol

from rhesis.telemetry.conversation import ConversationTurn, conversation_turn

from docs_assistant.state import ConversationState

MAX_CONVERSATIONS = 256
IDLE_TTL_SECONDS = 1800
# Names the turn root in the trace viewer; must stay under function.* or ai.*.
TURN_SPAN_NAME = "function.docs_assistant_turn"


@contextmanager
def traced_turn(conversation_id: str, message: str) -> Iterator[ConversationTurn]:
    """The turn root span carrying the conversation id, the message and (set by the caller) the
    reply. Behind @endpoint, Rhesis already owns the root, so this only binds the id. Without a
    Rhesis tracer provider it records nothing."""
    with conversation_turn(conversation_id, input=message, name=TURN_SPAN_NAME) as turn:
        yield turn


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
        # Turns holding or waiting on each lock. ``Lock.locked()`` can read False while waiters
        # are still queued, so only this count says when a lock is safe to drop.
        self._users: dict[str, int] = {}
        # Bumped by delete(), so a turn that loaded state before the delete doesn't save it back.
        self._generations: dict[str, int] = {}

    @asynccontextmanager
    async def turn(self, conversation_id: str | None) -> AsyncIterator[ConversationState]:
        """Hold the conversation's lock for one turn. An unknown or expired id starts fresh."""
        conversation_id = conversation_id or uuid.uuid4().hex
        lock = self._locks.setdefault(conversation_id, asyncio.Lock())
        self._users[conversation_id] = self._users.get(conversation_id, 0) + 1
        try:
            async with lock:
                generation = self._generations.get(conversation_id, 0)
                state = self._get(conversation_id) or ConversationState(conversation_id)
                try:
                    yield state
                finally:
                    if self._generations.get(conversation_id, 0) == generation:
                        self._put(state)
        finally:
            self._users[conversation_id] -= 1
            if not self._users[conversation_id]:
                del self._users[conversation_id]
                self._generations.pop(conversation_id, None)
                if conversation_id not in self._states:
                    self._locks.pop(conversation_id, None)

    def get(self, conversation_id: str) -> ConversationState | None:
        return self._get(conversation_id)

    def list(self) -> dict[str, int]:
        self._expire()
        return {cid: state.turn for cid, (state, _) in self._states.items()}

    def delete(self, conversation_id: str) -> bool:
        if conversation_id in self._users:
            self._generations[conversation_id] = self._generations.get(conversation_id, 0) + 1
        self._drop_lock(conversation_id)
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
        # A lock with a turn holding or waiting on it stays, so those turns still run one at a time.
        if conversation_id not in self._users:
            self._locks.pop(conversation_id, None)
