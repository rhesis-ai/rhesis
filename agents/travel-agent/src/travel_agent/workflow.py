"""Per-turn construction of the multi-agent handoff graph.

The graph is rebuilt for every turn because its shape depends on the brief: only the
specialists the router deems eligible are wired in, so the coordinator's handoff tools
are exactly the moves that make sense right now. On a conversational turn no specialists
are wired at all and the coordinator is left holding only its terminal tools.
"""

from __future__ import annotations

from typing import Any

from agent_framework import Agent, Workflow
from agent_framework_orchestrations import HandoffBuilder

from travel_agent.agents import SPECIALIST_FACTORIES, create_coordinator
from travel_agent.client import build_chat_client
from travel_agent.router import eligible_targets
from travel_agent.safety import SafetyVerdict
from travel_agent.state import TripBrief

WORKFLOW_NAME = "travel_agent_handoff"
WORKFLOW_DESCRIPTION = (
    "Travel Agent: a coordinator talks to the user and routes research to place, "
    "sightseeing, dining, weather, transit and lodging specialists."
)

# Retry nudge for a specialist that replies with text instead of handing back. Without it
# the turn would end at the specialist and the coordinator would never write the reply.
HANDBACK_PROMPT = (
    "Call handoff_to_trip_coordinator now to return control. Do not reply with more text."
)
SPECIALIST_TURN_LIMIT = 2


def build_travel_workflow(
    brief: TripBrief,
    message: str,
    *,
    verdict: SafetyVerdict | None = None,
    client: Any | None = None,
) -> Workflow:
    """Build this turn's workflow for ``brief`` and the user's ``message``."""
    chat_client = client if client is not None else build_chat_client()

    coordinator = create_coordinator(chat_client, verdict)
    names = eligible_targets(brief, message)
    specialists: list[Agent] = [SPECIALIST_FACTORIES[name](chat_client) for name in names]

    builder = HandoffBuilder(
        name=WORKFLOW_NAME,
        participants=[coordinator, *specialists],
        description=WORKFLOW_DESCRIPTION,
    ).with_start_agent(coordinator)

    if specialists:
        builder = builder.add_handoff(coordinator, specialists)
        for specialist in specialists:
            builder = builder.add_handoff(specialist, [coordinator])
        # Autonomous mode covers the specialists only. The coordinator stays non-autonomous
        # so its first reply without a handoff ends the run, instead of MAF re-prompting it
        # to "continue assisting" until the turn limit.
        builder = builder.with_autonomous_mode(
            agents=specialists,
            prompts={name: HANDBACK_PROMPT for name in names},
            turn_limits={name: SPECIALIST_TURN_LIMIT for name in names},
        )

    return builder.build()


def get_participants(workflow: Workflow) -> list[Agent]:
    """Return the participating ``Agent`` instances on a built workflow."""
    try:
        executors = workflow.executors  # type: ignore[attr-defined]
        agents: list[Agent] = []
        for executor in executors.values() if hasattr(executors, "values") else []:
            agent = getattr(executor, "agent", None)
            if isinstance(agent, Agent):
                agents.append(agent)
        return agents
    except Exception:  # noqa: BLE001
        return []


__all__ = [
    "HANDBACK_PROMPT",
    "SPECIALIST_TURN_LIMIT",
    "WORKFLOW_DESCRIPTION",
    "WORKFLOW_NAME",
    "build_travel_workflow",
    "get_participants",
]
