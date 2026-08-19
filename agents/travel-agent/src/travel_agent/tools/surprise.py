"""Surprise-destination picker.

The one tool with no external service behind it. It only names a city; the place
resolver still has to geocode it, which is what gives the rest of the pipeline the
coordinates it needs.
"""

from __future__ import annotations

from random import choice

from agent_framework import tool

from travel_agent.brief import current_brief
from travel_agent.state import set_destination

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
    """Pick a random vacation destination when the user asks to be surprised."""
    brief = current_brief()
    picked = choice(DESTINATIONS)
    city, _, country = picked.partition(",")
    set_destination(brief, city.strip(), country=country.strip() or None)
    return f"Picked {picked} as the surprise destination."


SURPRISE_TOOLS = [get_random_destination]

__all__ = ["DESTINATIONS", "SURPRISE_TOOLS", "get_random_destination"]
