"""Restaurant lookup via the Overpass API (OpenStreetMap, no API key).

Overpass lets us filter on cuisine and dietary tags, so a genuinely impossible request
("vegan traditional fondue") comes back empty from the real data rather than being
hallucinated into existence.
"""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from travel_agent.brief import current_brief
from travel_agent.state import (
    clear_no_results,
    clear_unavailable,
    find_leg,
    mark_no_results,
    mark_unavailable,
    primary_leg,
)
from travel_agent.tools import base

SERVICE = "dining"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

SEARCH_RADIUS_METRES = 3_000
MAX_RESULTS = 8

_DIET_TAGS = {
    "vegan": "diet:vegan",
    "vegetarian": "diet:vegetarian",
    "halal": "diet:halal",
    "kosher": "diet:kosher",
    "gluten_free": "diet:gluten_free",
}


def _build_query(lat: float, lon: float, cuisine: str, diet: str) -> str:
    filters = ""
    if cuisine.strip():
        # Overpass regex match, so "fondue" also hits "swiss;fondue".
        filters += f'["cuisine"~"{cuisine.strip().casefold()}",i]'
    diet_tag = _DIET_TAGS.get(diet.strip().casefold())
    if diet_tag:
        filters += f'["{diet_tag}"~"yes|only"]'
    return (
        "[out:json][timeout:10];"
        f'node(around:{SEARCH_RADIUS_METRES},{lat},{lon})["amenity"="restaurant"]{filters};'
        f"out {MAX_RESULTS};"
    )


def _names_from_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    names: list[str] = []
    for element in payload.get("elements") or []:
        if not isinstance(element, dict):
            continue
        name = ((element.get("tags") or {}).get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names[:MAX_RESULTS]


@tool
async def find_dining(
    city: Annotated[str, Field(description="City to search, exactly as it appears in the brief.")],
    cuisine: Annotated[
        str, Field(description="Cuisine to filter on, e.g. 'fondue', 'ramen'. Empty for any.")
    ] = "",
    diet: Annotated[
        str,
        Field(description="Dietary requirement: vegan, vegetarian, halal, kosher, gluten_free."),
    ] = "",
) -> str:
    """Find real restaurants near a city, optionally filtered by cuisine and diet."""
    brief = current_brief()
    leg = find_leg(brief, city) or primary_leg(brief)
    if leg is None:
        return "No destination is on file yet, so there is nothing to search for restaurants near."

    # Nothing recorded: this is a missing precondition, not an outage. ``pending_specialists``
    # already withholds coordinate-based lookups until the leg is geocoded.
    if leg.lat is None or leg.lon is None:
        return f"{leg.label} has no coordinates on file, so restaurants could not be looked up."

    outcome = await base.http_get_json(
        SERVICE,
        OVERPASS_URL,
        params={"data": _build_query(leg.lat, leg.lon, cuisine, diet)},
    )

    if outcome.failed:
        mark_unavailable(brief, SERVICE, outcome.detail)
        return (
            f"The restaurant search is unavailable ({outcome.detail}). "
            "Tell the user and continue planning without specific venues."
        )

    names = _names_from_payload(outcome.payload)
    criteria = " and ".join(part for part in (cuisine.strip(), diet.strip()) if part)

    if not names:
        clear_unavailable(brief, SERVICE)
        # A real empty result, not a failure: the service is up, so it stays reachable, but the
        # same search is not scheduled again until the trip changes.
        mark_no_results(brief, SERVICE, f"no {criteria or 'matching'} restaurants")
        return (
            f"The search found no {criteria or 'matching'} restaurants in {leg.label}. "
            "This is a genuine zero-result, not an error: tell the user plainly that "
            "nothing matched, "
            "explain briefly why it may be rare, and offer a nearby alternative to search instead. "
            "Do not invent venue names."
        )

    clear_unavailable(brief, SERVICE)
    clear_no_results(brief, SERVICE)
    leg.dining = names
    return f"Found {len(names)} {criteria or ''} places to eat in {leg.label}: {', '.join(names)}."


DINING_TOOLS = [find_dining]

__all__ = ["DINING_TOOLS", "MAX_RESULTS", "SERVICE", "find_dining"]
