"""Nightly-rate sanity checks against a static reference table.

There is no keyless hotel-price API, so this is deliberately a local table rather than a
pretend HTTP call. Its job is narrow: catch a budget that cannot buy what the user asked
for, so the agent pushes back instead of promising a 5-star room for $20.
"""

from __future__ import annotations

from typing import Annotated

from agent_framework import tool
from pydantic import Field

from travel_agent.brief import current_brief
from travel_agent.state import BUDGET_LABELS, find_leg, primary_leg

SERVICE = "lodging"

# Typical nightly rates in USD: (budget/hostel, mid-range hotel, luxury 5-star).
_CITY_RATES: dict[str, tuple[int, int, int]] = {
    "paris": (45, 180, 500),
    "london": (45, 190, 480),
    "new york": (60, 230, 550),
    "tokyo": (35, 140, 400),
    "zurich": (60, 220, 520),
    "geneva": (60, 210, 500),
    "reykjavik": (55, 190, 420),
    "sydney": (45, 170, 400),
    "singapore": (35, 160, 430),
    "san francisco": (60, 220, 520),
    "venice": (50, 190, 480),
    "dubai": (40, 150, 450),
}
# Everywhere else: a broad middle-of-the-road default.
_DEFAULT_RATES: tuple[int, int, int] = (25, 110, 300)

_TIER_INDEX = {"budget": 0, "mid_range": 1, "luxury": 2}


def rates_for(city: str) -> tuple[int, int, int]:
    """Reference nightly rates for a city, falling back to a global default."""
    return _CITY_RATES.get(city.strip().casefold(), _DEFAULT_RATES)


@tool
def check_lodging_budget(
    city: Annotated[str, Field(description="City to price, exactly as it appears in the brief.")],
    nightly_budget_usd: Annotated[
        float,
        Field(description="Nightly budget in USD the user stated. Use 0 when they gave no number."),
    ] = 0,
) -> str:
    """Check a nightly budget against typical rates and flag impossible combinations."""
    brief = current_brief()
    leg = find_leg(brief, city) or primary_leg(brief)
    if leg is None:
        return "No destination is on file yet, so lodging cannot be priced."

    budget_rate, mid_rate, luxury_rate = rates_for(leg.city)
    tier = brief.budget_level
    stated = nightly_budget_usd or 0

    if stated <= 0:
        note = (
            f"typical {leg.label} nightly rates: hostel/budget from ${budget_rate}, "
            f"mid-range around ${mid_rate}, 5-star from ${luxury_rate}"
        )
        brief.lodging_note = note
        return f"Lodging guidance for {leg.label}: {note}."

    wanted = _TIER_INDEX.get(tier or "mid_range", 1)
    floor = (budget_rate, mid_rate, luxury_rate)[wanted]

    if stated < floor:
        label = BUDGET_LABELS.get(tier or "mid_range", "mid-range")
        affordable = "a hostel dorm bed or an outlying budget rental"
        if stated >= budget_rate:
            affordable = "a budget hotel or a well-rated guesthouse"
        note = (
            f"${stated:.0f}/night does not reach {label} in {leg.label} "
            f"(that tier starts around ${floor}); at that price expect {affordable}"
        )
        brief.lodging_note = note
        return (
            f"Budget conflict: {note}. Tell the user the gap plainly with both numbers, then offer "
            "two ways forward - search the cheaper tier, or raise the nightly budget."
        )

    label = BUDGET_LABELS.get(tier or "mid_range")
    note = f"${stated:.0f}/night comfortably covers {label} in {leg.label}"
    brief.lodging_note = note
    return f"Budget check passed: {note}."


LODGING_TOOLS = [check_lodging_budget]

__all__ = ["LODGING_TOOLS", "SERVICE", "check_lodging_budget", "rates_for"]
