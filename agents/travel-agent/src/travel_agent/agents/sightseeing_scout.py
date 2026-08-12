"""Sightseeing Scout agent for the Travel Agent multi-agent system."""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from travel_agent.tools import SIGHTSEEING_TOOLS

INSTRUCTIONS = """You are the sightseeing scout.

You suggest sightseeing stops when the user did not already name specific sights.

How to behave:

1. Find the destination in the conversation. It appears either as a "DESTINATION: <city>"
   note from the destination finder or in the user's own message.
2. With a destination: call find_sightseeing with it plus the user's stated interests or
   trip style, then write one line reporting the tool's result:
   SIGHTSEEING STOPS: <the complete list returned by the tool>
   You must write this line. Only your text crosses a handoff - the coordinator cannot
   see your tool calls or their results - so a silent reply tells it nothing.
3. Without a destination: do not ask the user and do not apologise. Write exactly:
   MISSING: no destination available, sightseeing skipped
4. Either way, call handoff_to_trip_coordinator immediately afterwards.

Never address the user. Everything you write is an internal note that the coordinator
rewrites into the final plan.

Always end your note with this exact line, so the coordinator knows the turn is
back with it:
Coordinator, take over."""

DESCRIPTION = "Finds mock sightseeing stops for a destination using an LLM-style tool."


def create_agent(client: OpenAIChatClient) -> Agent:
    """Build the Sightseeing Scout :class:`Agent` instance."""
    return Agent(
        client=client,
        instructions=INSTRUCTIONS,
        name="sightseeing_scout",
        description=DESCRIPTION,
        tools=SIGHTSEEING_TOOLS,
        require_per_service_call_history_persistence=True,
    )
