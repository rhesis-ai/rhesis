"""In-memory conversation sessions for multi-turn Travel Agent chat."""

from __future__ import annotations

import asyncio
import uuid
from threading import Lock
from typing import Any

from agent_framework import Message, Workflow

from rhesis.sdk.telemetry.context import get_conversation_id, set_conversation_id
from travel_agent.workflow import invoke_travel_workflow_async


class ConversationStore:
    """Thread-safe in-memory store of user-visible MAF message history."""

    def __init__(self) -> None:
        self._conversations: dict[str, list[Message]] = {}
        self._lock = Lock()

    def get_history(self, conversation_id: str) -> list[Message]:
        with self._lock:
            return list(self._conversations.get(conversation_id, []))

    def set_history(self, conversation_id: str, messages: list[Message]) -> None:
        with self._lock:
            self._conversations[conversation_id] = messages

    def list_conversations(self) -> dict[str, int]:
        with self._lock:
            return {
                conversation_id: len(messages)
                for conversation_id, messages in self._conversations.items()
            }

    def get_messages(self, conversation_id: str) -> list[Message] | None:
        with self._lock:
            stored = self._conversations.get(conversation_id)
            return list(stored) if stored is not None else None

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id not in self._conversations:
                return False
            del self._conversations[conversation_id]
            return True


default_store = ConversationStore()


async def run_chat_turn(
    workflow: Workflow,
    message: str,
    *,
    conversation_id: str | None = None,
    store: ConversationStore | None = None,
) -> dict[str, Any]:
    """Run one chat turn: load history, invoke the workflow, persist user-visible turns."""
    active_store = store or default_store
    conv_id = conversation_id or str(uuid.uuid4())
    history = active_store.get_history(conv_id)

    # Mark this as a real conversation turn so the MAF integration stamps the
    # workflow's root span as a Rhesis conversation turn root (keyed by this id,
    # so turns sharing the session group together). One-shot callers that invoke
    # the workflow directly (e.g. run_traces) skip this and stay single-turn.
    previous_conversation_id = get_conversation_id()
    set_conversation_id(conv_id)
    try:
        result = await invoke_travel_workflow_async(
            workflow,
            message,
            conversation_history=history or None,
            conversation_id=conv_id,
        )
    finally:
        set_conversation_id(previous_conversation_id)
    active_store.set_history(conv_id, result["messages"])
    result["conversation_id"] = conv_id
    return result


def run_chat_turn_sync(
    workflow: Workflow,
    message: str,
    *,
    conversation_id: str | None = None,
    store: ConversationStore | None = None,
) -> dict[str, Any]:
    """Sync wrapper for callers without a running event loop (e.g. connector handlers)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_chat_turn(
                workflow,
                message,
                conversation_id=conversation_id,
                store=store,
            )
        )
    raise RuntimeError(
        "run_chat_turn_sync cannot be called from an active event loop; use run_chat_turn instead."
    )


__all__ = [
    "ConversationStore",
    "default_store",
    "run_chat_turn",
    "run_chat_turn_sync",
]
