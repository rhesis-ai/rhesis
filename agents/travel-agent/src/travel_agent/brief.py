"""Ambient trip brief: how state crosses a handoff.

MAF's ``clean_conversation_for_handoff`` strips function calls and results from the
conversation at every hop, so a specialist's findings cannot reach the coordinator
through the transcript. Instead the brief is bound to the turn as a ``ContextVar``,
tools mutate it as a side effect of running, and a ``ContextProvider`` re-renders it
into each agent's instructions on every activation.

The brief is bound once per turn and mutated in place. Never call ``set()`` mid-turn:
an ``asyncio.Task`` copies the context at creation, so a rebind inside a workflow
executor would be invisible to everything outside that task. Mutating the object the
var already points at is shared by everyone, which is what we want.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from agent_framework import ContextProvider

from travel_agent.state import TripBrief, render_brief

BRIEF_SOURCE_ID = "trip_brief"

_current_brief: ContextVar[TripBrief | None] = ContextVar("travel_agent_brief", default=None)


@contextmanager
def bind_brief(brief: TripBrief) -> Iterator[TripBrief]:
    """Bind ``brief`` for the duration of one turn."""
    token = _current_brief.set(brief)
    try:
        yield brief
    finally:
        _current_brief.reset(token)


def current_brief() -> TripBrief:
    """The brief for the running turn.

    Raises:
        RuntimeError: if called outside :func:`bind_brief`. Tools depend on this, so a
            missing binding is a wiring bug that should fail loudly rather than silently
            write to a throwaway object.
    """
    brief = _current_brief.get()
    if brief is None:
        raise RuntimeError(
            "No trip brief is bound. Tools and context providers must run inside bind_brief()."
        )
    return brief


class BriefContextProvider(ContextProvider):
    """Injects the live brief into every agent activation.

    Attached to all agents. ``HandoffBuilder._clone_chat_agent`` forwards
    ``context_providers`` to the clones it builds, so this survives graph construction
    and fires on each hop.
    """

    def __init__(self, source_id: str = BRIEF_SOURCE_ID) -> None:
        super().__init__(source_id)

    async def before_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
    ) -> None:
        context.extend_instructions(self.source_id, render_brief(current_brief()))


__all__ = [
    "BRIEF_SOURCE_ID",
    "BriefContextProvider",
    "bind_brief",
    "current_brief",
]
