"""Weather outlook via Open-Meteo (no API key).

The canonical degradation case: when this is unreachable the agent says so once and
plans the trip anyway.
"""

from __future__ import annotations

import statistics
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

SERVICE = "weather"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes, collapsed to the distinctions a traveller actually packs for.
_WET_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
_SNOW_CODES = {71, 73, 75, 77, 85, 86}


def _summarise(daily: dict[str, Any]) -> str:
    highs = [value for value in daily.get("temperature_2m_max") or [] if value is not None]
    lows = [value for value in daily.get("temperature_2m_min") or [] if value is not None]
    codes = [code for code in daily.get("weather_code") or [] if code is not None]
    if not highs or not lows:
        return ""

    high = round(statistics.mean(highs))
    low = round(statistics.mean(lows))
    wet_days = sum(1 for code in codes if code in _WET_CODES)
    snow_days = sum(1 for code in codes if code in _SNOW_CODES)

    parts = [f"highs around {high}C, lows around {low}C"]
    if snow_days:
        parts.append(f"snow likely on {snow_days} of {len(codes)} days - pack waterproof boots")
    elif wet_days:
        parts.append(f"rain on {wet_days} of {len(codes)} days - bring a waterproof layer")
    elif codes:
        parts.append("mostly dry")
    return "; ".join(parts)


@tool
async def get_weather(
    city: Annotated[str, Field(description="City to check, exactly as it appears in the brief.")],
) -> str:
    """Get the 7-day weather outlook for a city already in the trip brief."""
    brief = current_brief()
    leg = find_leg(brief, city) or primary_leg(brief)
    if leg is None:
        return "No destination is on file yet, so there is nothing to check the weather for."

    # Nothing recorded: this is a missing precondition, not an outage. ``pending_specialists``
    # already withholds coordinate-based lookups until the leg is geocoded.
    if leg.lat is None or leg.lon is None:
        return (
            f"{leg.label} has no coordinates on file, so the forecast could not be looked up. "
            "Plan without weather detail."
        )

    outcome = await base.http_get_json(
        SERVICE,
        OPEN_METEO_URL,
        params={
            "latitude": leg.lat,
            "longitude": leg.lon,
            "daily": "temperature_2m_max,temperature_2m_min,weather_code",
            "forecast_days": 7,
            "timezone": "auto",
        },
    )

    if outcome.failed:
        mark_unavailable(brief, SERVICE, outcome.detail)
        return (
            f"The weather service is unreachable ({outcome.detail}). "
            f"Tell the user the forecast is unavailable and plan {leg.label} without it."
        )

    payload = outcome.payload if isinstance(outcome.payload, dict) else {}
    summary = _summarise(payload.get("daily") or {})
    if not summary:
        mark_no_results(brief, SERVICE, "no forecast returned")
        return f"The weather service returned no forecast for {leg.label}. Plan without it."

    clear_unavailable(brief, SERVICE)
    clear_no_results(brief, SERVICE)
    leg.weather = summary
    return f"Weather outlook for {leg.label}: {summary}."


WEATHER_TOOLS = [get_weather]

__all__ = ["SERVICE", "WEATHER_TOOLS", "get_weather"]
