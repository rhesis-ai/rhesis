"""Agent factories for the Travel Agent multi-agent system."""

from travel_agent.agents.coordinator import create_agent as create_coordinator
from travel_agent.agents.destination_finder import create_agent as create_destination_finder
from travel_agent.agents.logistics_planner import create_agent as create_logistics_planner
from travel_agent.agents.sightseeing_scout import create_agent as create_sightseeing_scout

ALL_AGENT_NAMES: list[str] = [
    "trip_coordinator",
    "destination_finder",
    "sightseeing_scout",
    "logistics_planner",
]

__all__ = [
    "ALL_AGENT_NAMES",
    "create_coordinator",
    "create_destination_finder",
    "create_logistics_planner",
    "create_sightseeing_scout",
]
