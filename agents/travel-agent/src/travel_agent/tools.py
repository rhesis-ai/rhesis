"""Mock tools for the Microsoft Agent Framework travel multi-agent demo."""

from __future__ import annotations

from random import randint
from typing import Annotated

from agent_framework import tool
from pydantic import Field

DESTINATIONS: list[str] = [
    "Barcelona, Spain",
    "Paris, France",
    "Berlin, Germany",
    "Tokyo, Japan",
    "Sydney, Australia",
    "New York, USA",
    "Cairo, Egypt",
    "Cape Town, South Africa",
    "Rio de Janeiro, Brazil",
    "Bali, Indonesia",
]


@tool
def get_random_destination() -> str:
    """Get a random vacation destination."""
    return DESTINATIONS[randint(0, len(DESTINATIONS) - 1)]


@tool
def find_sightseeing(
    destination: Annotated[str, Field(description="The city or destination to explore.")],
    interests: Annotated[
        str,
        Field(description="The user's travel interests, constraints, or trip style."),
    ] = "general sightseeing",
) -> str:
    """Return mock sightseeing suggestions for a destination."""
    return (
        f"For {destination}, prioritize these sightseeing stops based on {interests}: "
        "the historic old town, the main art or history museum, the central market, "
        "a scenic viewpoint, and one relaxed neighborhood walk."
    )


@tool
def estimate_travel(
    destination: Annotated[str, Field(description="The city or destination for the trip.")],
    attractions: Annotated[
        str,
        Field(description="Comma-separated sightseeing stops or areas to estimate around."),
    ],
) -> str:
    """Return mock relative distance and travel-time estimates for sightseeing stops."""
    return (
        f"Mock logistics for {destination}: from the central station, the listed stops "
        f"({attractions}) are roughly 10-25 minutes apart by public transit or taxi. "
        "From the city center, plan 5-15 minutes between nearby sights and 25-40 minutes "
        "to outer neighborhoods. From the airport, allow 35-60 minutes to reach the first stop."
    )


DESTINATION_TOOLS = [get_random_destination]
SIGHTSEEING_TOOLS = [find_sightseeing]
LOGISTICS_TOOLS = [estimate_travel]

__all__ = [
    "DESTINATIONS",
    "DESTINATION_TOOLS",
    "LOGISTICS_TOOLS",
    "SIGHTSEEING_TOOLS",
    "estimate_travel",
    "find_sightseeing",
    "get_random_destination",
]
