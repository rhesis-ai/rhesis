"""Sightseeing Scout agent for the Travel Agent multi-agent system."""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from travel_agent.tools import SIGHTSEEING_TOOLS

INSTRUCTIONS = """You are the sightseeing scout.

You suggest sightseeing stops when the user did not already name specific sights.

How to behave:

1. Call find_sightseeing with the destination and the user's stated interests or trip style.
2. Immediately call handoff_to_trip_coordinator to return the sightseeing list.
   Do not send user-facing prose; the coordinator presents the stops to the user."""

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
