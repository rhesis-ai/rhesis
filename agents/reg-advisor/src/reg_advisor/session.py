"""In-memory conversation sessions for multi-turn Reg-Advisor chat."""

from __future__ import annotations

import asyncio
import uuid
from threading import Lock
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from rhesis.telemetry.conversation import conversation_turn

from reg_advisor.runner import APP_NAME, build_coordinator_agent, run_turn, run_turn_async
from reg_advisor.state import RegAdvisorState


class StateStore:
    """Thread-safe in-memory store of :class:`RegAdvisorState` keyed by conversation id.

    Turns on one conversation must serialize, or two overlapping turns read the same state and
    the second write loses the first. Both a sync and an async lock are offered per conversation
    because the two entry points cannot share one: a ``threading.Lock`` held across an ``await``
    blocks the whole event loop, and the coroutine holding it can never resume. That is a
    permanent hang, not a slow request.
    """

    def __init__(self, *, max_conversations: int = 256) -> None:
        self._states: dict[str, RegAdvisorState] = {}
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

    def get(self, conversation_id: str) -> RegAdvisorState:
        with self._lock:
            return self._states.get(conversation_id, RegAdvisorState()).model_copy(deep=True)

    def set(self, conversation_id: str, state: RegAdvisorState) -> None:
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


# Names the turn root in the trace viewer. Must stay under the ``function.`` or
# ``ai.`` namespace or the backend rejects the span.
TURN_SPAN_NAME = "function.reg_advisor_turn"

default_store = StateStore()

_default_agent: LlmAgent | None = None
_agent_init_lock = Lock()


def get_default_agent() -> LlmAgent:
    """Return the process-wide coordinator agent tree, building it once on first use.

    The agent tree is the expensive part — four ``LlmAgent`` instances and every tool schema —
    and concurrent turns share this one instance with no run lock. That rests on ADK holding no
    per-run state in it: ``LlmAgent`` makes no assignment to ``self`` anywhere, ``canonical_model``
    and ``canonical_tools`` resolve on each call rather than caching onto the instance, and
    ``Runner.run_async`` keeps its bookkeeping in the per-invocation ``InvocationContext``. The
    one mutation is ``Gemini.api_client``, a ``cached_property``: two threads can race to build
    it, both get a valid client and one wins. That client is ``google-genai``'s, built on
    ``httpx.Client``, which is safe to share across threads.

    What is *not* shared is the ``Runner`` and its ``InMemorySessionService`` — see
    :func:`build_turn_runner`.
    """
    global _default_agent
    if _default_agent is None:
        with _agent_init_lock:
            if _default_agent is None:
                _default_agent = build_coordinator_agent()
    return _default_agent


def build_turn_runner(agent: LlmAgent | None = None) -> Runner:
    """Build a runner for one turn, around the shared agent.

    A fresh ``Runner`` and ``InMemorySessionService`` per turn, deliberately. ADK's in-memory
    session service is three plain nested dicts with no locking at all, so a shared one would
    race on concurrent turns — and, because each turn creates a session it never deletes, it
    would also grow without bound on a long-running server. Both problems disappear if the
    scratch space lives and dies with the turn. The objects are cheap; the agent tree they wrap
    is what gets reused.
    """
    return Runner(
        app_name=APP_NAME,
        agent=agent or get_default_agent(),
        session_service=InMemorySessionService(),
    )


def run_chat_turn(
    message: str,
    *,
    conversation_id: str | None = None,
    store: StateStore | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Run one chat turn: load state, invoke the coordinator, persist updates."""
    active_store = store or default_store
    conv_id = conversation_id or str(uuid.uuid4())

    # Own the turn so the trace carries what the user actually saw. The reply is
    # not always the model's last message -- a terminal tool, a refusal or a
    # briefing composes it -- so no framework integration can recover it, and ADK's
    # own run span has already ended by the time we hold it.
    with conversation_turn(conv_id, input=message, name=TURN_SPAN_NAME) as turn:
        with active_store.conversation_lock(conv_id):
            state = active_store.get(conv_id)
            result = run_turn(message, state, runner=runner or build_turn_runner())
            active_store.set(conv_id, result["state"])
        turn.output = result["response"]

    result["conversation_id"] = conv_id
    return result


async def run_chat_turn_async(
    message: str,
    *,
    conversation_id: str | None = None,
    store: StateStore | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Async variant, serialized per conversation but concurrent across conversations."""
    active_store = store or default_store
    conv_id = conversation_id or str(uuid.uuid4())

    # Stands down to just binding the conversation id when @endpoint already owns
    # the turn root, which is the served path in app.py.
    with conversation_turn(conv_id, input=message, name=TURN_SPAN_NAME) as turn:
        async with active_store.async_conversation_lock(conv_id):
            state = active_store.get(conv_id)
            result = await run_turn_async(message, state, runner=runner or build_turn_runner())
            active_store.set(conv_id, result["state"])
        turn.output = result["response"]

    result["conversation_id"] = conv_id
    return result


__all__ = [
    "TURN_SPAN_NAME",
    "StateStore",
    "build_turn_runner",
    "default_store",
    "get_default_agent",
    "run_chat_turn",
    "run_chat_turn_async",
]
