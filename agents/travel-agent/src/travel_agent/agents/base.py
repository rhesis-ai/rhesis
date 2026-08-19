"""Shared agent construction.

Every agent gets the same three things: the brief provider so it can see the live trip
state, the fault middleware so a broken tool degrades instead of killing the turn, and
per-service-call history persistence, which ``HandoffBuilder`` requires of all
participants.
"""

from __future__ import annotations

from typing import Any

from agent_framework import Agent

from travel_agent.brief import BriefContextProvider
from travel_agent.faults import ToolFaultMiddleware

# Specialists are told this rather than being asked to summarise their findings in prose.
# Their tools write straight into the brief, and the brief is re-injected into the
# coordinator's instructions on its next activation, so a report would be redundant - and
# under MAF's handoff rules only text survives the hop, which is what made the old
# labelled-line protocol so fragile.
HANDBACK_RULE = """\
Your tool writes its results into the trip brief, so the coordinator already sees them.
Do not repeat the findings and do not summarise them.

When your tool has run - or if it could not run - call handoff_to_trip_coordinator
immediately. Write at most one short sentence before you do.

Never address the user. The coordinator writes everything the user reads."""


def build_agent(
    client: Any,
    *,
    name: str,
    description: str,
    instructions: str,
    tools: list[Any] | None = None,
    extra_providers: list[Any] | None = None,
) -> Agent:
    """Build an agent wired with the brief provider and tool fault guard."""
    return Agent(
        client=client,
        instructions=instructions,
        name=name,
        description=description,
        tools=tools or [],
        context_providers=[BriefContextProvider(), *(extra_providers or [])],
        middleware=[ToolFaultMiddleware()],
        require_per_service_call_history_persistence=True,
    )


def build_specialist(
    client: Any,
    *,
    name: str,
    description: str,
    role: str,
    tools: list[Any],
) -> Agent:
    """Build a specialist: its own short role paragraph plus the shared handback rule."""
    return build_agent(
        client,
        name=name,
        description=description,
        instructions=f"{role.strip()}\n\n{HANDBACK_RULE}",
        tools=tools,
    )


__all__ = ["HANDBACK_RULE", "build_agent", "build_specialist"]
