"""Destination Finder agent for the Travel Agent multi-agent system."""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from travel_agent.tools import DESTINATION_TOOLS

INSTRUCTIONS = """You are the destination finder.

You choose a city for trips when the coordinator needs a destination.

How to behave:

1. Call get_random_destination. Do not choose a city without using the tool.
2. Reply with the selected destination in one short sentence.
3. You must end every turn by calling the handoff_to_trip_coordinator tool. Do not reply
   with plain text only and do not keep talking after handing off."""

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
