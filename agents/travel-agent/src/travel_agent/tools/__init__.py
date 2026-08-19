"""Travel Agent tools: one module per external service.

Every tool returns a plain sentence and never raises. Failures are written onto the trip
brief as ``unavailable`` entries so the rest of the conversation can route around them.
"""

from travel_agent.tools.base import (
    ToolOutcome,
    ToolStatus,
    active_faults,
    http_get_json,
    parse_faults,
)
from travel_agent.tools.dining import DINING_TOOLS, find_dining
from travel_agent.tools.lodging import LODGING_TOOLS, check_lodging_budget, rates_for
from travel_agent.tools.places import PLACE_TOOLS, choose_candidate, resolve_destination
from travel_agent.tools.routing import ROUTING_TOOLS, estimate_travel
from travel_agent.tools.sights import SIGHTS_TOOLS, find_sightseeing
from travel_agent.tools.surprise import DESTINATIONS, SURPRISE_TOOLS, get_random_destination
from travel_agent.tools.weather import WEATHER_TOOLS, get_weather

__all__ = [
    "DESTINATIONS",
    "DINING_TOOLS",
    "LODGING_TOOLS",
    "PLACE_TOOLS",
    "ROUTING_TOOLS",
    "SIGHTS_TOOLS",
    "SURPRISE_TOOLS",
    "WEATHER_TOOLS",
    "ToolOutcome",
    "ToolStatus",
    "active_faults",
    "check_lodging_budget",
    "choose_candidate",
    "estimate_travel",
    "find_dining",
    "find_sightseeing",
    "get_random_destination",
    "get_weather",
    "http_get_json",
    "parse_faults",
    "rates_for",
    "resolve_destination",
]
