"""Landmark lookup via the Overpass API (OpenStreetMap, no API key).

Wikipedia's GeoSearch was the obvious first choice and turned out to be the wrong data:
it returns *articles near a point*, so a city-centre coordinate comes back as a list of
downtown office towers. OpenStreetMap tags what a place actually is, so asking for
``tourism=attraction`` and friends returns things people visit.
"""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from travel_agent.brief import current_brief
from travel_agent.state import (
    Sight,
    clear_no_results,
    clear_unavailable,
    find_leg,
    is_excluded,
    mark_no_results,
    mark_unavailable,
    primary_leg,
)
from travel_agent.tools import base

SERVICE = "sights"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

SEARCH_RADIUS_METRES = 6_000
MAX_SIGHTS = 8
# Over-fetch so the picks can be spread across the radius instead of clustering on
# whichever street the city-centre coordinate landed on.
SEARCH_LIMIT = 60

# What counts as worth seeing, as OpenStreetMap tags it. Nodes only: asking for ways and
# relations as well makes the query several times more expensive, and the public Overpass
# endpoint answers those with a 504 often enough to matter.
_TOURISM = "attraction|museum|gallery|viewpoint|zoo|theme_park|aquarium"
_HISTORIC = "castle|monument|memorial|ruins|palace|archaeological_site"

# Wikipedia article titles that are never a place you visit.
_NOISE_PREFIXES = ("List of", "Timeline of", "History of", "Outline of", "Index of")
# Downtown coordinates are dense with commercial and civic buildings nobody visits, and
# Wikipedia has an article for every one of them.
_NOISE_TERMS = (
    "station",
    "office",
    "headquarters",
    "parking",
    "hospital",
    "embassy",
    "ministry",
    "diocese",
    "corporation",
    " inc",
    " ltd",
    "building",
)


def _build_query(lat: float, lon: float) -> str:
    around = f"around:{SEARCH_RADIUS_METRES},{lat},{lon}"
    return (
        "[out:json][timeout:20];("
        f'node({around})["tourism"~"{_TOURISM}"]["name"];'
        f'node({around})["historic"~"{_HISTORIC}"]["name"];'
        f");out {SEARCH_LIMIT};"
    )


def _sight_from_element(element: dict[str, Any]) -> Sight | None:
    name = ((element.get("tags") or {}).get("name") or "").strip()
    if not name:
        return None
    centre = element.get("center") or {}
    lat = element.get("lat", centre.get("lat"))
    lon = element.get("lon", centre.get("lon"))
    return Sight(name=name, lat=lat, lon=lon)


def _spread(sights: list[Sight], limit: int) -> list[Sight]:
    """Take an evenly spaced sample so the picks are not all one block apart."""
    if len(sights) <= limit:
        return sights
    stride = len(sights) / limit
    return [sights[int(index * stride)] for index in range(limit)]


def _sights_from_payload(payload: Any) -> list[Sight]:
    if not isinstance(payload, dict):
        return []
    sights: list[Sight] = []
    seen: set[str] = set()
    for element in payload.get("elements") or []:
        if not isinstance(element, dict):
            continue
        sight = _sight_from_element(element)
        if sight is None or sight.name.casefold() in seen:
            continue
        seen.add(sight.name.casefold())
        sights.append(sight)
    return sights


def _is_visitable(title: str) -> bool:
    if any(title.startswith(prefix) for prefix in _NOISE_PREFIXES):
        return False
    lowered = title.casefold()
    if any(term in lowered for term in _NOISE_TERMS):
        return False
    return not title.strip().isdigit()


def _sights_from_wikipedia(payload: Any) -> list[Sight]:
    if not isinstance(payload, dict):
        return []
    results = (payload.get("query") or {}).get("geosearch") or []
    sights: list[Sight] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        title = str(result.get("title") or "").strip()
        if title and _is_visitable(title):
            sights.append(Sight(name=title, lat=result.get("lat"), lon=result.get("lon")))
    return sights


async def _from_overpass(lat: float, lon: float) -> tuple[list[Sight], str]:
    outcome = await base.http_get_json(
        SERVICE, OVERPASS_URL, params={"data": _build_query(lat, lon)}
    )
    if outcome.failed:
        return [], outcome.detail
    return _sights_from_payload(outcome.payload), ""


async def _from_wikipedia(lat: float, lon: float) -> tuple[list[Sight], str]:
    outcome = await base.http_get_json(
        SERVICE,
        WIKIPEDIA_API_URL,
        params={
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": 10_000,
            "gslimit": SEARCH_LIMIT,
            "format": "json",
        },
    )
    if outcome.failed:
        return [], outcome.detail
    return _sights_from_wikipedia(outcome.payload), ""


@tool
async def find_sightseeing(
    city: Annotated[str, Field(description="City to search, exactly as it appears in the brief.")],
) -> str:
    """Find real landmarks and attractions near a city already in the trip brief."""
    brief = current_brief()
    leg = find_leg(brief, city) or primary_leg(brief)
    if leg is None:
        return "No destination is on file yet, so there is nothing to find sights for."

    # Nothing recorded: this is a missing precondition, not an outage. ``pending_specialists``
    # already withholds coordinate-based lookups until the leg is geocoded.
    if leg.lat is None or leg.lon is None:
        return (
            f"{leg.label} has no coordinates on file, so landmarks could not be looked up. "
            "Suggest well-known highlights from general knowledge instead, and say "
            "they are not verified."
        )

    # OpenStreetMap knows what a place *is*, so it is the better answer - but the public
    # Overpass endpoint is genuinely unreliable. Wikipedia's GeoSearch is always up and
    # merely less precise, which makes it a good second choice rather than no answer.
    found, detail = await _from_overpass(leg.lat, leg.lon)
    if not found:
        found, detail = await _from_wikipedia(leg.lat, leg.lon)

    sights = _spread([s for s in found if not is_excluded(brief, s.name)], MAX_SIGHTS)

    if not sights:
        # ``detail`` is only set when a source failed, so an empty one means a source answered
        # and simply had nothing - or everything it had was excluded.
        if detail:
            mark_unavailable(brief, SERVICE, detail)
        else:
            mark_no_results(brief, SERVICE, "no landmarks found")
        return (
            f"The landmark search came back empty for {leg.label} ({detail or 'no matches'}). "
            f"Tell the user, then suggest well-known {leg.label} highlights from general "
            "knowledge and say they are not verified."
        )

    clear_unavailable(brief, SERVICE)
    clear_no_results(brief, SERVICE)
    leg.sights = sights
    names = ", ".join(sight.name for sight in sights)
    return f"Found {len(sights)} landmarks near {leg.label}: {names}."


SIGHTS_TOOLS = [find_sightseeing]

__all__ = ["MAX_SIGHTS", "SEARCH_LIMIT", "SERVICE", "SIGHTS_TOOLS", "find_sightseeing"]
