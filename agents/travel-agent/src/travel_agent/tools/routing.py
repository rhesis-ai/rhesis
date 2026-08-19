"""Travel times via the OSRM demo server (no API key).

Uses the duration matrix from the city centre to each sight, so "20 minutes across town"
is a measured number rather than a guess. The public demo host is best-effort and does
fall over, which is exactly the partial-failure case the agent has to survive.
"""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from travel_agent.brief import current_brief
from travel_agent.state import Sight, clear_unavailable, find_leg, mark_unavailable, primary_leg
from travel_agent.tools import base

SERVICE = "transit"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/"

MAX_WAYPOINTS = 8


def _located(sights: list[Sight]) -> list[Sight]:
    return [sight for sight in sights if sight.lat is not None and sight.lon is not None]


def _summarise(sights: list[Sight], durations: list[float | None]) -> str:
    minutes = [
        (sight.name, round(duration / 60))
        for sight, duration in zip(sights, durations, strict=False)
        if duration is not None
    ]
    if not minutes:
        return ""

    times = [value for _, value in minutes]
    low, high = min(times), max(times)
    if low == high:
        # Naming a "closest" and a "farthest" here would describe a spread that is not
        # there - it reads as nonsense when every stop measured the same.
        return f"all the stops are about {high} minutes from the city centre by road"

    nearest = min(minutes, key=lambda item: item[1])
    farthest = max(minutes, key=lambda item: item[1])
    return (
        f"from the city centre the stops are {low}-{high} minutes away by road "
        f"({nearest[0]} is closest at {nearest[1]} min, "
        f"{farthest[0]} farthest at {farthest[1]} min)"
    )


@tool
async def estimate_travel(
    city: Annotated[
        str, Field(description="City to route within, exactly as it appears in the brief.")
    ],
) -> str:
    """Estimate travel times from the city centre to each sight already in the brief."""
    brief = current_brief()
    leg = find_leg(brief, city) or primary_leg(brief)
    if leg is None:
        return "No destination is on file yet, so there is nothing to estimate travel for."

    if leg.lat is None or leg.lon is None:
        mark_unavailable(brief, SERVICE, "destination has no map coordinates")
        return f"{leg.label} has no coordinates on file, so travel times could not be measured."

    sights = _located(leg.sights)[:MAX_WAYPOINTS]
    if not sights:
        return (
            f"No located sightseeing stops are on file for {leg.label} yet, "
            "so there is nothing to measure travel time between."
        )

    coordinates = ";".join(
        [f"{leg.lon},{leg.lat}", *(f"{sight.lon},{sight.lat}" for sight in sights)]
    )
    outcome = await base.http_get_json(
        SERVICE,
        f"{OSRM_TABLE_URL}{coordinates}",
        params={"sources": "0", "annotations": "duration"},
    )

    if outcome.failed:
        mark_unavailable(brief, SERVICE, outcome.detail)
        return (
            f"The routing service is unreachable ({outcome.detail}). "
            "Tell the user exact travel times are unavailable, then give rough guidance: "
            "central stops are usually 10-25 minutes apart by transit, outer ones 25-40."
        )

    payload: Any = outcome.payload if isinstance(outcome.payload, dict) else {}
    matrix = payload.get("durations") or []
    row = matrix[0] if matrix else []
    # First column is the origin to itself; the rest line up with ``sights``.
    summary = _summarise(sights, list(row[1:]))

    if not summary:
        mark_unavailable(brief, SERVICE, "no route found")
        return (
            f"The routing service returned no usable route for {leg.label}. "
            "Give rough guidance instead."
        )

    clear_unavailable(brief, SERVICE)
    leg.transit = summary
    return f"Travel times for {leg.label}: {summary}."


ROUTING_TOOLS = [estimate_travel]

__all__ = ["MAX_WAYPOINTS", "ROUTING_TOOLS", "SERVICE", "estimate_travel"]
