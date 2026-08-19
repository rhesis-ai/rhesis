"""Agent factories for the Travel Agent multi-agent system."""

from travel_agent.agents.base import build_agent, build_specialist
from travel_agent.agents.coordinator import create_coordinator
from travel_agent.agents.specialists import (
    SPECIALIST_FACTORIES,
    create_conditions_scout,
    create_destination_finder,
    create_dining_scout,
    create_lodging_advisor,
    create_place_resolver,
    create_sightseeing_scout,
    create_transit_planner,
)

ALL_AGENT_NAMES: list[str] = ["trip_coordinator", *SPECIALIST_FACTORIES]

__all__ = [
    "ALL_AGENT_NAMES",
    "SPECIALIST_FACTORIES",
    "build_agent",
    "build_specialist",
    "create_conditions_scout",
    "create_coordinator",
    "create_destination_finder",
    "create_dining_scout",
    "create_lodging_advisor",
    "create_place_resolver",
    "create_sightseeing_scout",
    "create_transit_planner",
]
