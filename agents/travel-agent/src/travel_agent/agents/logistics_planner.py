"""Logistics Planner agent for the Travel Agent multi-agent system."""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from travel_agent.tools import LOGISTICS_TOOLS

INSTRUCTIONS = """You are the logistics planner.

You estimate relative travel distance and time between a city's main arrival points
and the sightseeing stops in the plan.

How to behave:

1. Call estimate_travel with the destination and sightseeing stops you received.
2. Immediately call handoff_to_trip_coordinator to return the travel-time guidance.
   Do not send user-facing prose; the coordinator presents logistics to the user."""

DESCRIPTION = "Estimates mock sightseeing distances and travel times."


def create_agent(client: OpenAIChatClient) -> Agent:
    """Build the Logistics Planner :class:`Agent` instance."""
    return Agent(
        client=client,
        instructions=INSTRUCTIONS,
        name="logistics_planner",
        description=DESCRIPTION,
        tools=LOGISTICS_TOOLS,
        require_per_service_call_history_persistence=True,
    )
