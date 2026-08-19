"""The six research specialists, one per external service.

Each one owns a single lookup and hands control straight back. They are deliberately
thin: all the judgement lives in the coordinator, and all the findings live in the brief.
"""

from __future__ import annotations

from typing import Any

from agent_framework import Agent

from travel_agent.agents.base import build_specialist
from travel_agent.tools.dining import DINING_TOOLS
from travel_agent.tools.lodging import LODGING_TOOLS
from travel_agent.tools.places import PLACE_TOOLS
from travel_agent.tools.routing import ROUTING_TOOLS
from travel_agent.tools.sights import SIGHTS_TOOLS
from travel_agent.tools.surprise import SURPRISE_TOOLS
from travel_agent.tools.weather import WEATHER_TOOLS


def create_destination_finder(client: Any) -> Agent:
    """Picks a surprise destination."""
    return build_specialist(
        client,
        name="destination_finder",
        description="Picks a random surprise destination.",
        role=(
            "You are the destination finder. The user wants to be surprised.\n\n"
            "Call get_random_destination once. Do not choose a city yourself."
        ),
        tools=SURPRISE_TOOLS,
    )


def create_place_resolver(client: Any) -> Agent:
    """Geocodes the destination and detects ambiguous city names."""
    return build_specialist(
        client,
        name="place_resolver",
        description="Resolves a place name to a real city and flags ambiguous names.",
        role=(
            "You are the place resolver. You turn the destination in the brief into a real city "
            "with map coordinates, which every later lookup depends on.\n\n"
            "Call resolve_destination with the destination exactly as it appears in the brief."
        ),
        tools=PLACE_TOOLS,
    )


def create_sightseeing_scout(client: Any) -> Agent:
    """Finds real landmarks near the destination."""
    return build_specialist(
        client,
        name="sightseeing_scout",
        description="Finds real landmarks near the destination via Wikipedia GeoSearch.",
        role=(
            "You are the sightseeing scout.\n\n"
            "Call find_sightseeing once for each city in the brief that has no sightseeing yet."
        ),
        tools=SIGHTS_TOOLS,
    )


def create_dining_scout(client: Any) -> Agent:
    """Finds restaurants matching the user's food interests."""
    return build_specialist(
        client,
        name="dining_scout",
        description="Finds real restaurants by cuisine and diet via OpenStreetMap.",
        role=(
            "You are the dining scout.\n\n"
            "Call find_dining for the city in the brief, passing the cuisine and any dietary "
            "requirement from the user's interests. If it returns nothing, that is a real answer - "
            "leave it as is and let the coordinator explain."
        ),
        tools=DINING_TOOLS,
    )


def create_conditions_scout(client: Any) -> Agent:
    """Checks the weather outlook."""
    return build_specialist(
        client,
        name="conditions_scout",
        description="Checks the weather outlook via Open-Meteo.",
        role=(
            "You are the conditions scout.\n\n"
            "Call get_weather once for each city in the brief that has no weather yet."
        ),
        tools=WEATHER_TOOLS,
    )


def create_transit_planner(client: Any) -> Agent:
    """Measures travel times between the sights."""
    return build_specialist(
        client,
        name="transit_planner",
        description="Measures real travel times from the city centre to each sight via OSRM.",
        role=(
            "You are the transit planner.\n\n"
            "Call estimate_travel once for each city in the brief that already has sightseeing "
            "stops but no travel times."
        ),
        tools=ROUTING_TOOLS,
    )


def create_lodging_advisor(client: Any) -> Agent:
    """Sanity-checks the nightly budget."""
    return build_specialist(
        client,
        name="lodging_advisor",
        description="Checks a nightly budget against typical rates for the city.",
        role=(
            "You are the lodging advisor.\n\n"
            "Call check_lodging_budget for the city in the brief. Pass the nightly figure the user "
            "gave in US dollars, or 0 if they gave none."
        ),
        tools=LODGING_TOOLS,
    )


SPECIALIST_FACTORIES = {
    "destination_finder": create_destination_finder,
    "place_resolver": create_place_resolver,
    "sightseeing_scout": create_sightseeing_scout,
    "dining_scout": create_dining_scout,
    "conditions_scout": create_conditions_scout,
    "transit_planner": create_transit_planner,
    "lodging_advisor": create_lodging_advisor,
}

__all__ = [
    "SPECIALIST_FACTORIES",
    "create_conditions_scout",
    "create_destination_finder",
    "create_dining_scout",
    "create_lodging_advisor",
    "create_place_resolver",
    "create_sightseeing_scout",
    "create_transit_planner",
]
