"""Shared trip state for the Travel Agent.

The brief is the agent's memory. It is the only thing that survives a handoff intact:
MAF's ``clean_conversation_for_handoff`` strips tool calls and results from the
conversation at every hop, so anything the specialists learn has to live here rather
than in the prose they write.

Pure Pydantic and pure functions - no framework imports, so this module is trivially
testable and can be reasoned about without running an agent.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

BudgetLevel = Literal["budget", "mid_range", "luxury"]

# Services the specialists depend on. Used as keys in ``TripBrief.unavailable`` so a
# failed lookup is remembered for the rest of the conversation instead of being retried
# on every turn and failing again.
SERVICES: tuple[str, ...] = ("places", "sights", "dining", "weather", "transit", "lodging")

# ``resolution_attempts`` values that mean the *name* cannot be planned for, as opposed to the
# geocoder being unreachable. The distinction matters because the two need opposite responses: an
# unplaceable name has to go back to the user, while a timed-out lookup leaves a perfectly good
# name on file and must not send the conversation back to ask which city.
UNPLACEABLE_REASONS: frozenset[str] = frozenset({"empty", "no match", "country, not a city"})

# Interest words that make a dining lookup worth a handoff.
FOOD_TERMS: tuple[str, ...] = (
    "food",
    "eat",
    "dining",
    "restaurant",
    "culinary",
    "cuisine",
    "vegan",
    "vegetarian",
    "street food",
    "foodie",
)

BUDGET_LABELS: dict[str, str] = {
    "budget": "budget",
    "mid_range": "mid-range",
    "luxury": "luxury",
}


class Phase(str, Enum):
    """Where the conversation is. Always derived from the brief, never asserted by the model."""

    GREETING = "greeting"
    RESOLVING = "resolving"
    GATHERING = "gathering"
    BUILDING = "building"
    PLANNED = "planned"


class PlaceCandidate(BaseModel):
    """One possible reading of an ambiguous place name (Portland OR vs Portland ME)."""

    label: str
    country: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    # Nominatim's prominence score, used to tell a real ambiguity from a famous city that
    # merely shares its name with a small town.
    importance: float | None = None


class Sight(BaseModel):
    """A place worth visiting. Coordinates are kept so the transit lookup can route to it."""

    name: str
    lat: float | None = None
    lon: float | None = None


class TripLeg(BaseModel):
    """One city in the trip. Single-city trips are a one-leg list."""

    city: str
    country: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    days: int | None = None
    interests: list[str] = Field(default_factory=list)
    sights: list[Sight] = Field(default_factory=list)
    dining: list[str] = Field(default_factory=list)
    weather: str | None = None
    transit: str | None = None

    @property
    def label(self) -> str:
        """Human-readable city name, qualified by region/country when we have it."""
        parts = [self.city, self.region, self.country]
        return ", ".join(part for part in parts if part)


class TripBrief(BaseModel):
    """Everything known about the trip so far.

    Mutated in place during a turn (one turn holds it at a time, under the session lock)
    and snapshotted back into the store only when the turn succeeds.
    """

    legs: list[TripLeg] = Field(default_factory=list)
    candidates: list[PlaceCandidate] = Field(default_factory=list)
    budget_level: BudgetLevel | None = None
    excluded_interests: list[str] = Field(default_factory=list)
    lodging_note: str | None = None
    # service -> why it is unusable, e.g. {"weather": "request timed out"}.
    unavailable: dict[str, str] = Field(default_factory=dict)
    # service -> why a completed lookup found nothing, e.g. {"sights": "no landmarks found"}.
    # Deliberately not ``unavailable``: the service answered, so the router keeps offering the
    # specialist and a later change to the trip can retry it.
    no_results: dict[str, str] = Field(default_factory=dict)
    plan_text: str | None = None
    # Set by a terminal tool; when present it *is* the reply and no plan is written.
    pending_reply: str | None = None
    # What the user said this turn. Carried here because a handoff does not reliably put
    # the user's own message in front of the agent that receives control.
    last_user_message: str | None = None
    # Place names already sent to the geocoder, and how that went. Stops a name the
    # geocoder cannot place from being retried on every hop for the rest of the session.
    resolution_attempts: dict[str, str] = Field(default_factory=dict)
    turn: int = 0


def is_blank(value: str | None) -> bool:
    """True when a value is unset or only whitespace, i.e. not real content."""
    return value is None or not value.strip()


def primary_leg(brief: TripBrief) -> TripLeg | None:
    """The leg the conversation is currently about - the first one."""
    return brief.legs[0] if brief.legs else None


def find_leg(brief: TripBrief, city: str) -> TripLeg | None:
    """Look up a leg by city name, case-insensitively."""
    wanted = city.strip().casefold()
    for leg in brief.legs:
        if leg.city.casefold() == wanted:
            return leg
    return None


def set_destination(
    brief: TripBrief,
    city: str,
    *,
    country: str | None = None,
    region: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    days: int | None = None,
    replace: bool = True,
) -> TripLeg:
    """Record a destination, replacing the current trip unless ``replace`` is False.

    ``replace=True`` is the mid-session pivot (Rome -> Barcelona): the old itinerary is
    dropped but the trip length carries over, because "same timeframe" is the common case
    and the user should not have to restate it. ``replace=False`` appends a leg for
    multi-city trips.
    """
    if is_blank(city):
        raise ValueError("city must not be blank")

    existing = find_leg(brief, city)
    if existing is not None:
        leg = existing
    else:
        leg = TripLeg(city=city.strip())
        if replace:
            carried_days = (
                days if days is not None else (brief.legs[0].days if brief.legs else None)
            )
            leg.days = carried_days
            brief.legs = [leg]
        else:
            brief.legs.append(leg)

    if not is_blank(country):
        leg.country = country
    if not is_blank(region):
        leg.region = region
    if lat is not None:
        leg.lat = lat
    if lon is not None:
        leg.lon = lon
    if days is not None:
        leg.days = days

    # A resolved destination settles any pending ambiguity.
    brief.candidates = []
    # New place, or coordinates for an old one: anything that found nothing deserves a retry.
    brief.no_results.clear()
    return leg


def add_interests(brief: TripBrief, interests: list[str], *, city: str | None = None) -> None:
    """Add interests to a leg, dropping blanks and anything the user has excluded."""
    leg = find_leg(brief, city) if city else primary_leg(brief)
    if leg is None:
        return
    excluded = {item.casefold() for item in brief.excluded_interests}
    added = False
    for interest in interests:
        cleaned = interest.strip()
        if is_blank(cleaned) or cleaned.casefold() in excluded:
            continue
        if cleaned.casefold() not in {existing.casefold() for existing in leg.interests}:
            leg.interests.append(cleaned)
            added = True

    # Sights and dining both search on interests, so a new one is a different search - and
    # an empty result for the old one says nothing about it. Restating a known interest is
    # not a change, so it does not buy another attempt.
    if added:
        clear_no_results(brief, "sights")
        clear_no_results(brief, "dining")


def exclusion_terms(brief: TripBrief) -> set[str]:
    """Substrings that mark a place as unwanted.

    A user who says "museums" means the "Museum of Fine Arts" too, so each term is also
    matched in its singular form. Short terms are dropped: a three-letter substring
    matches far too much to be safe.
    """
    terms: set[str] = set()
    for item in brief.excluded_interests:
        for variant in (item.casefold(), item.casefold().removesuffix("s")):
            if len(variant) >= 4:
                terms.add(variant)
    return terms


def is_excluded(brief: TripBrief, name: str) -> bool:
    """Whether a place name matches something the user ruled out."""
    lowered = name.casefold()
    return any(term in lowered for term in exclusion_terms(brief))


def exclude_interests(brief: TripBrief, unwanted: list[str]) -> None:
    """Record dislikes and purge them from every leg's interests and sights.

    Negative feedback has to reach the sights too, otherwise the next plan rebuilds from
    an itinerary the user just rejected.
    """
    for item in unwanted:
        cleaned = item.strip()
        if is_blank(cleaned):
            continue
        if cleaned.casefold() not in {existing.casefold() for existing in brief.excluded_interests}:
            brief.excluded_interests.append(cleaned)

    # Different exclusions can change what a search returns, so let those two run again.
    clear_no_results(brief, "sights")
    clear_no_results(brief, "dining")

    excluded = {item.casefold() for item in brief.excluded_interests}
    for leg in brief.legs:
        leg.interests = [i for i in leg.interests if i.casefold() not in excluded]
        leg.sights = [s for s in leg.sights if not is_excluded(brief, s.name)]


def mark_unavailable(brief: TripBrief, service: str, reason: str) -> None:
    """Remember that a service could not be reached, so the plan can say so and move on."""
    brief.unavailable[service] = reason.strip() or "unavailable"


def clear_unavailable(brief: TripBrief, service: str) -> None:
    """Forget a past failure after a successful call."""
    brief.unavailable.pop(service, None)


def mark_no_results(brief: TripBrief, service: str, reason: str) -> None:
    """Remember that a lookup completed but found nothing, so it is not re-run unchanged.

    Kept out of ``unavailable`` on purpose. A service that answers with nothing is not down,
    so the router must keep the specialist reachable; this only stops the same lookup being
    scheduled again while its inputs are identical.
    """
    brief.no_results[service] = reason.strip() or "nothing found"


def clear_no_results(brief: TripBrief, service: str) -> None:
    """Forget a past empty result, so a changed trip searches again."""
    brief.no_results.pop(service, None)


def derive_phase(brief: TripBrief) -> Phase:
    """Work out the phase from what is actually in the brief.

    Order matters: an unresolved ambiguity outranks everything, because planning against
    the wrong Portland is worse than planning nothing.
    """
    if brief.candidates:
        return Phase.RESOLVING
    if not brief.legs:
        return Phase.GREETING
    if needs_a_real_city(brief):
        return Phase.GATHERING
    if any(leg.days is None for leg in brief.legs):
        return Phase.GATHERING
    if brief.plan_text:
        return Phase.PLANNED
    return Phase.BUILDING


def missing_slots(brief: TripBrief) -> list[str]:
    """Slots still worth asking about, most important first.

    Only ``destination`` and ``duration`` block planning. Interests and budget are asked
    for once but never gate the plan - scenario 15 ("you decide") has to be able to
    proceed on defaults.
    """
    missing: list[str] = []
    if not brief.legs:
        missing.append("destination")
        return missing
    if needs_a_real_city(brief):
        # Nothing else is worth asking while the destination cannot be placed on a map.
        return ["city"]
    if any(leg.days is None for leg in brief.legs):
        missing.append("duration")
    if not any(leg.interests for leg in brief.legs):
        missing.append("interests")
    if brief.budget_level is None:
        missing.append("budget")
    return missing


def needs_resolution(brief: TripBrief) -> bool:
    """Whether the place resolver still has work worth doing.

    Coordinates gate everything downstream, so this is worth a hop - but only once per
    name. A name the geocoder could not place will not be placed on a retry, and retrying
    it was what turned a single bad lookup into a routing loop. A name it never got to look
    at, because the service timed out, is still worth another go.
    """
    if brief.candidates:
        return False  # waiting on the user to choose, not on the resolver
    leg = primary_leg(brief)
    if leg is None:
        return True  # nothing recorded yet; the user may be naming a place this turn
    if leg.lat is not None:
        return False
    return brief.resolution_attempts.get(leg.city) not in UNPLACEABLE_REASONS


def needs_a_real_city(brief: TripBrief) -> bool:
    """Whether the destination on file cannot be planned for and the user must narrow it.

    True once the geocoder has been asked and could not place the name - "Japan" is a
    country, "Zzzz" is nothing. Every coordinate-based lookup would fail against it, so
    the conversation has to go back to the user rather than build around a dead end.

    Keyed on *why* the attempt failed, not on the presence of an attempt. A geocoder that
    timed out has said nothing about the name: treating that as unplannable sent the
    coordinator back to ask which city with the city already on file, and answering it
    recorded the same name and asked again.
    """
    return any(
        leg.lat is None and brief.resolution_attempts.get(leg.city) in UNPLACEABLE_REASONS
        for leg in brief.legs
    )


def wants_food(brief: TripBrief) -> bool:
    """Whether the user showed any interest in food, which is what makes dining worth a hop."""
    return any(
        any(term in interest.casefold() for term in FOOD_TERMS)
        for leg in brief.legs
        for interest in leg.interests
    )


def pending_specialists(brief: TripBrief) -> list[str]:
    """Build steps that still have work to do, in dependency order.

    Returned in the order they must run: transit routes between sights, so it only
    becomes pending once the scout has found some. Steps whose service is already known
    to be down are dropped rather than retried - that is what keeps a dead API from
    costing a hop on every subsequent turn.
    """
    pending: list[str] = []
    if not brief.legs:
        return pending

    def up(service: str) -> bool:
        """Worth a hop: not known down, and not already searched for nothing."""
        return service not in brief.unavailable and service not in brief.no_results

    # Sights, dining, weather and routing are all coordinate-based. Without a geocoded
    # destination they cannot succeed, so scheduling them would spend a hop to learn that.
    located = [leg for leg in brief.legs if leg.lat is not None]

    if any(not leg.sights for leg in located) and up("sights"):
        pending.append("sightseeing_scout")
    if wants_food(brief) and any(not leg.dining for leg in located) and up("dining"):
        pending.append("dining_scout")
    if any(leg.weather is None for leg in located) and up("weather"):
        pending.append("conditions_scout")
    if any(leg.sights and leg.transit is None for leg in located) and up("transit"):
        pending.append("transit_planner")
    if brief.budget_level is not None and brief.lodging_note is None and up("lodging"):
        pending.append("lodging_advisor")
    return pending


def _leg_lines(brief: TripBrief) -> list[str]:
    lines: list[str] = []
    for index, leg in enumerate(brief.legs, 1):
        prefix = f"- Stop {index}: " if len(brief.legs) > 1 else "- Destination: "
        duration = f"{leg.days} days" if leg.days is not None else "length not set"
        lines.append(f"{prefix}{leg.label} ({duration})")
        if leg.interests:
            lines.append(f"  interests: {', '.join(leg.interests)}")
        sights = ", ".join(sight.name for sight in leg.sights)
        lines.append(f"  sightseeing: {sights or 'not gathered yet'}")
        if leg.dining:
            lines.append(f"  dining: {', '.join(leg.dining)}")
        if leg.weather:
            lines.append(f"  weather: {leg.weather}")
        if leg.transit:
            lines.append(f"  getting around: {leg.transit}")
    return lines


def render_brief(brief: TripBrief) -> str:
    """Render the brief for injection into every agent's instructions.

    This is the single most important prompt surface in the system: it is what replaces
    the prose protocol the specialists used to serialise their findings into. Keep it
    short and literal - a weak model has to be able to read it without interpretation.
    """
    phase = derive_phase(brief)
    lines: list[str] = []
    if brief.last_user_message:
        lines.append(f'The user just said: "{brief.last_user_message}"')
    lines.append("TRIP BRIEF - what is already on file. Never ask again for anything listed here.")

    if not brief.legs and not brief.candidates:
        lines.append("- Nothing on file yet.")
    lines.extend(_leg_lines(brief))

    if brief.candidates:
        options = "; ".join(candidate.label for candidate in brief.candidates)
        lines.append(f"- Destination is ambiguous, waiting for the user to pick: {options}")
    if brief.budget_level:
        lines.append(f"- Budget: {BUDGET_LABELS[brief.budget_level]}")
    if brief.excluded_interests:
        lines.append(f"- Ruled out, never suggest: {', '.join(brief.excluded_interests)}")
    if brief.lodging_note:
        lines.append(f"- Lodging: {brief.lodging_note}")
    if brief.unavailable:
        notes = "; ".join(f"{service} ({reason})" for service, reason in brief.unavailable.items())
        lines.append(
            f"- Unavailable this session: {notes}. "
            "Say so plainly once, then carry on planning without it. "
            "Never retry and never invent it."
        )
    if brief.no_results:
        notes = "; ".join(f"{service} ({reason})" for service, reason in brief.no_results.items())
        lines.append(
            f"- Searched, found nothing: {notes}. "
            "Say so plainly once and plan around it. Repeating the same search is pointless, "
            "but searching for something different is fine."
        )
    if brief.plan_text:
        lines.append("- A plan has already been given to the user; this turn is a refinement.")

    lines.append(f"Phase: {phase.value}")
    still_needed = missing_slots(brief)
    lines.append(f"Still needed: {', '.join(still_needed) if still_needed else 'nothing'}")
    return "\n".join(lines)


def render_plan(brief: TripBrief) -> str:
    """Assemble a plan from the brief with no LLM involved.

    The degraded path: used when the coordinator burns through its hop budget without
    producing a reply. Everything needed is already in the brief, so a turn that loops
    still ends with something honest and useful rather than an error.
    """
    leg_count = len(brief.legs)
    if leg_count == 0:
        return (
            "I don't have a destination on file yet. Tell me where you'd like to go - "
            "or ask me to surprise you - and I'll put a plan together."
        )

    total_days = sum(leg.days or 0 for leg in brief.legs)
    where = " then ".join(leg.label for leg in brief.legs)
    header = (
        f"Here's your {total_days}-day plan for {where}."
        if total_days
        else f"Here's your plan for {where}."
    )
    lines = [header]

    for leg in brief.legs:
        lines.append("")
        duration = f" ({leg.days} days)" if leg.days else ""
        lines.append(f"{leg.label}{duration}")
        if leg.sights:
            lines.append("Sightseeing stops:")
            lines.extend(f"- {sight.name}" for sight in leg.sights)
        if leg.dining:
            lines.append(f"Places to eat: {', '.join(leg.dining)}")
        if leg.weather:
            lines.append(f"Weather: {leg.weather}.")
        if leg.transit:
            lines.append(f"Getting around: {leg.transit}.")

    if brief.lodging_note:
        lines.extend(["", f"Lodging: {brief.lodging_note}."])
    if brief.unavailable:
        services = ", ".join(brief.unavailable)
        lines.extend(
            [
                "",
                f"One note: I couldn't reach the {services} service, "
                "so that detail is missing here.",
            ]
        )

    lines.extend(["", "Tell me what you'd like to change and I'll adjust it."])
    return "\n".join(lines)


__all__ = [
    "BUDGET_LABELS",
    "FOOD_TERMS",
    "SERVICES",
    "UNPLACEABLE_REASONS",
    "BudgetLevel",
    "Phase",
    "PlaceCandidate",
    "Sight",
    "TripBrief",
    "TripLeg",
    "add_interests",
    "clear_no_results",
    "clear_unavailable",
    "derive_phase",
    "exclude_interests",
    "exclusion_terms",
    "find_leg",
    "is_blank",
    "is_excluded",
    "mark_no_results",
    "mark_unavailable",
    "missing_slots",
    "needs_a_real_city",
    "needs_resolution",
    "pending_specialists",
    "primary_leg",
    "render_brief",
    "render_plan",
    "set_destination",
    "wants_food",
]
