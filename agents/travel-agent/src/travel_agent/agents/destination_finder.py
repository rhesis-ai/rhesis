"""Destination Finder agent for the Travel Agent multi-agent system."""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from travel_agent.tools import DESTINATION_TOOLS

INSTRUCTIONS = """You are the destination finder.

You choose a city for trips when the coordinator needs a destination.

How to behave:

1. Call get_random_destination. Do not choose a city without using the tool.
2. Write one line reporting the tool's result exactly as returned:
   DESTINATION: <city returned by the tool>
   You must write this line. Only your text crosses a handoff - the coordinator cannot
   see your tool calls or their results - so a silent reply tells it nothing.
3. Immediately call handoff_to_trip_coordinator.

Never address the user. Everything you write is an internal note that the coordinator
rewrites into the final plan.

Always end your note with this exact line, so the coordinator knows the turn is
back with it:
Coordinator, take over."""

DESCRIPTION = "Selects a random travel destination with get_random_destination."


def create_agent(client: OpenAIChatClient) -> Agent:
    """Build the Destination Finder :class:`Agent` instance."""
    return Agent(
        client=client,
        instructions=INSTRUCTIONS,
        name="destination_finder",
        description=DESCRIPTION,
        tools=DESTINATION_TOOLS,
        require_per_service_call_history_persistence=True,
    )
