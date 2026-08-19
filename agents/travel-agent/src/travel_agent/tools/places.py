"""Destination resolution via Nominatim (OpenStreetMap).

Resolving the place first is what makes the rest of the pipeline possible: the weather,
sights and dining lookups are all coordinate-based. It also surfaces genuine ambiguity -
"Portland" really is two well-known cities - which the agent must ask about rather than
guess at.
"""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from travel_agent.brief import current_brief
from travel_agent.state import PlaceCandidate, clear_unavailable, mark_unavailable, set_destination
from travel_agent.tools import base
from travel_agent.tools.base import ToolOutcome

SERVICE = "places"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Only settlements are plausible trip destinations; Nominatim also returns streets,
# buildings and shops for the same query. "province" and "state" are in here because
# several major cities are administrative regions in their own right - Tokyo comes back
# as a province, Berlin and Singapore as states - and excluding them loses the
# destination entirely.
_SETTLEMENT_TYPES = {
    "city",
    "town",
    "village",
    "municipality",
    "administrative",
    "province",
    "prefecture",
    "state",
    "region",
    "county",
    "island",
    "borough",
}

# Where a settlement name can appear in Nominatim's address block, best first.
_NAME_KEYS = ("city", "town", "village", "municipality", "borough", "province", "county")


def _candidate_from_result(result: dict[str, Any]) -> PlaceCandidate | None:
    address = result.get("address") or {}
    city = next(
        (address[key] for key in _NAME_KEYS if address.get(key)),
        (result.get("name") or (result.get("display_name") or "").split(",")[0]).strip(),
    )
    if not city:
        return None
    try:
        lat = float(result["lat"])
        lon = float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return PlaceCandidate(
        label=city,
        country=address.get("country"),
        region=address.get("state") or address.get("region"),
        lat=lat,
        lon=lon,
        importance=result.get("importance"),
    )


def _distinct_candidates(payload: Any) -> list[PlaceCandidate]:
    """Settlement candidates from a Nominatim payload, deduped by (city, region, country)."""
    if not isinstance(payload, list):
        return []
    seen: set[tuple[str, str, str]] = set()
    candidates: list[PlaceCandidate] = []
    for result in payload:
        if not isinstance(result, dict):
            continue
        kind = result.get("addresstype") or result.get("type") or ""
        if kind not in _SETTLEMENT_TYPES:
            continue
        candidate = _candidate_from_result(result)
        if candidate is None:
            continue
        key = (
            candidate.label.casefold(),
            (candidate.region or "").casefold(),
            (candidate.country or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


# How close the runner-up must be to the top match before the name is worth querying.
# Nominatim's importance score is dominated by the well-known reading of a name: Rome,
# Italy far outranks Rome, New York, and asking which one the user meant would be pedantic.
# Portland OR and Portland ME sit close together, which is the case worth asking about.
AMBIGUITY_RATIO = 0.85


def _same_name_rivals(candidates: list[PlaceCandidate], query: str) -> list[PlaceCandidate]:
    """Candidates whose name matches the query closely enough to be genuinely ambiguous.

    Only same-name rivals count - "Tokyo" also returns unrelated far-away matches - and
    only ones of comparable prominence, or every famous city would trigger a question.
    """
    wanted = query.strip().casefold()
    rivals = [candidate for candidate in candidates if candidate.label.casefold() == wanted]
    if len(rivals) < 2:
        return rivals

    top = rivals[0].importance or 0.0
    if not top:
        return rivals
    return [rival for rival in rivals if (rival.importance or 0.0) >= top * AMBIGUITY_RATIO]


def _matches_a_country(payload: Any, query: str) -> bool:
    """Whether the query named a country rather than a city.

    Worth telling apart: every coordinate-based lookup needs a city, so "Japan" has to
    become a question rather than a destination we cannot plan for.
    """
    if not isinstance(payload, list):
        return False
    wanted = query.strip().casefold()
    for result in payload:
        if not isinstance(result, dict):
            continue
        kind = result.get("addresstype") or result.get("type") or ""
        if kind != "country":
            continue
        name = (result.get("address") or {}).get("country") or result.get("name") or ""
        if str(name).casefold() == wanted:
            return True
    return False


def _describe(candidate: PlaceCandidate) -> str:
    parts = [candidate.label, candidate.region, candidate.country]
    return ", ".join(part for part in parts if part)


async def _lookup(place: str) -> ToolOutcome:
    return await base.http_get_json(
        SERVICE,
        NOMINATIM_URL,
        params={
            "q": place,
            "format": "json",
            "limit": 8,
            "addressdetails": 1,
            # Without this Nominatim answers in the local script, and the brief would end
            # up carrying "東京都" as the destination name.
            "accept-language": "en",
        },
    )


@tool
async def resolve_destination(
    place: Annotated[
        str, Field(description="City or place name the user named, as they wrote it.")
    ],
) -> str:
    """Resolve a place name to a real city, detecting ambiguous names."""
    brief = current_brief()
    query = place.strip()
    if not query:
        return "No place name was given, so nothing could be resolved."

    outcome = await _lookup(query)
    # Remember we tried, whatever happens: the router uses this to stop routing back here
    # for a name the geocoder has already refused.
    brief.resolution_attempts[query] = outcome.status.value

    if outcome.failed:
        mark_unavailable(brief, SERVICE, outcome.detail)
        # Record the raw name anyway: a dead geocoder must not block planning, it only
        # costs us coordinates (and therefore weather and sights) for this session.
        set_destination(brief, query)
        return (
            f"The place lookup service is unavailable ({outcome.detail}). "
            f"Continuing with '{query}' as the destination, without map coordinates."
        )

    clear_unavailable(brief, SERVICE)
    candidates = _distinct_candidates(outcome.payload)

    if not candidates and _matches_a_country(outcome.payload, query):
        # Recorded, not removed. Deleting the leg only started a fight with the
        # coordinator, which recorded the country again on its next activation; the
        # attempt marker is what moves the conversation on to asking for a city.
        brief.resolution_attempts[query] = "country, not a city"
        return (
            f"'{query}' is a country, not a city. Ask the user which city in {query} they "
            "want to visit, and suggest two or three well-known options."
        )

    if not candidates:
        brief.resolution_attempts[query] = "no match"
        return (
            f"No city matching '{query}' was found. Ask the user to check the spelling "
            "or name a nearby larger city."
        )

    rivals = _same_name_rivals(candidates, query)
    if len(rivals) > 1:
        brief.candidates = rivals[:4]
        options = " or ".join(_describe(candidate) for candidate in brief.candidates)
        return (
            f"'{query}' is ambiguous - it matches {options}. "
            "Ask the user which one they mean before planning anything."
        )

    chosen = rivals[0] if rivals else candidates[0]
    set_destination(
        brief,
        chosen.label,
        country=chosen.country,
        region=chosen.region,
        lat=chosen.lat,
        lon=chosen.lon,
    )
    return f"Destination resolved to {_describe(chosen)}."


@tool
def choose_candidate(
    label: Annotated[
        str, Field(description="The candidate city the user picked, e.g. 'Portland'.")
    ],
    region: Annotated[
        str, Field(description="State or region that identifies which candidate, e.g. 'Oregon'.")
    ] = "",
) -> str:
    """Pick one of the ambiguous destination candidates the user was asked about."""
    brief = current_brief()
    if not brief.candidates:
        return "There are no pending destination candidates to choose from."

    wanted_region = region.strip().casefold()
    wanted_label = label.strip().casefold()
    for candidate in brief.candidates:
        matches_label = candidate.label.casefold() == wanted_label
        matches_region = not wanted_region or wanted_region in (candidate.region or "").casefold()
        if matches_label and matches_region:
            set_destination(
                brief,
                candidate.label,
                country=candidate.country,
                region=candidate.region,
                lat=candidate.lat,
                lon=candidate.lon,
            )
            return f"Destination set to {_describe(candidate)}."

    options = " or ".join(_describe(candidate) for candidate in brief.candidates)
    return f"That did not match a pending candidate. The options are {options}."


# The resolver only geocodes. Picking between candidates is a conversational act - the
# coordinator is the one who asked the question - so ``choose_candidate`` is a coordinator
# tool. Keeping it here would mean routing back to a specialist just to record an answer
# the user already gave.
PLACE_TOOLS = [resolve_destination]

__all__ = ["PLACE_TOOLS", "SERVICE", "choose_candidate", "resolve_destination"]
