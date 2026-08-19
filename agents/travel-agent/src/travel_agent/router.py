"""Per-turn routing: which specialists exist, and what the coordinator is told to do.

The workflow is rebuilt every turn, so the handoff topology can be chosen per turn. That
is the whole defence against the old failure mode: on a conversational turn the
coordinator is given *no* handoff tools at all, so "Hi" cannot reach a specialist and
cannot come back as an unasked-for itinerary. It is a structural guarantee rather than a
line in a prompt that a small model may ignore.

It also keeps the tool list short. Seven specialists offered at once is a lot of choice
for a weak model; two or three, chosen by what the brief is actually missing, is not.
"""

from __future__ import annotations

import re
from typing import Any

from agent_framework import ContextProvider

from travel_agent.brief import current_brief
from travel_agent.safety import TRAVEL_PATTERNS, SafetyVerdict, flag_note
from travel_agent.state import (
    Phase,
    TripBrief,
    derive_phase,
    missing_slots,
    pending_specialists,
    primary_leg,
)
from travel_agent.terminals import question_for

COORDINATOR_NAME = "trip_coordinator"

# Fixed order so the trace graph reads the same way every run.
SPECIALIST_ORDER: tuple[str, ...] = (
    "destination_finder",
    "place_resolver",
    "sightseeing_scout",
    "dining_scout",
    "conditions_scout",
    "transit_planner",
    "lodging_advisor",
)

SURPRISE_PATTERN = re.compile(
    r"\b(surprise|suprise|random|anywhere|you\s+(choose|decide|pick)|pick\s+(one|somewhere|for\s+me))\b",
    re.IGNORECASE,
)


def wants_surprise(message: str) -> bool:
    """Whether the user is asking us to choose the destination."""
    return bool(SURPRISE_PATTERN.search(message or ""))


def is_conversational(brief: TripBrief, message: str) -> bool:
    """True when this turn is chat, not planning, and no specialist should be reachable.

    Only ever true before a trip exists. Once the brief holds a destination, even a bare
    "ok" is a planning turn - which is what stops a short reply from dropping the trip.
    """
    if brief.legs or brief.candidates:
        return False
    if wants_surprise(message):
        return False
    return not TRAVEL_PATTERNS.search(message or "")


# Which brief service each specialist depends on, so one that is already known to be down
# is not offered as a destination for a handoff.
SPECIALIST_SERVICES: dict[str, str] = {
    "place_resolver": "places",
    "sightseeing_scout": "sights",
    "dining_scout": "dining",
    "conditions_scout": "weather",
    "transit_planner": "transit",
    "lodging_advisor": "lodging",
}


def eligible_targets(brief: TripBrief, message: str) -> list[str]:
    """Specialists to wire into this turn's graph.

    The graph is fixed for the whole turn, but the brief is not: a destination recorded
    mid-turn makes specialists relevant that were not relevant when the turn began. So
    this is deliberately generous on a planning turn and wires everything that could be
    needed, leaving the *order* to the directive, which is re-rendered on every hop.

    The one hard gate is conversational versus planning. A greeting gets no specialists at
    all, which is what makes "Hi" structurally incapable of returning an itinerary.
    """
    if is_conversational(brief, message):
        return []

    targets = set(SPECIALIST_ORDER)
    if not wants_surprise(message):
        targets.discard("destination_finder")
    for name, service in SPECIALIST_SERVICES.items():
        if service in brief.unavailable:
            targets.discard(name)

    return [name for name in SPECIALIST_ORDER if name in targets]


def _building_directive(brief: TripBrief, pending: list[str]) -> str:
    if not pending:
        return (
            "Everything needed is on file. Write the complete plan now as one self-contained "
            "message to the user. Do not hand off."
        )
    steps = " then ".join(pending)
    return (
        f"Research still needed. Hand off to {steps}, one at a time, waiting for each "
        "to come back. "
        "When none are left, write the complete plan as one self-contained message to the user."
    )


def coordinator_directive(
    brief: TripBrief,
    message: str,
    verdict: SafetyVerdict | None = None,
) -> str:
    """The short, phase-scoped instruction block for this turn.

    Everything the coordinator needs that is not already in the rendered brief: what
    phase it is in, which specialists exist right now, and the single next move.
    """
    phase = derive_phase(brief)
    lines = [f"THIS TURN - phase {phase.value}."]

    targets = eligible_targets(brief, message)
    if targets:
        lines.append(f"Specialists you can hand off to right now: {', '.join(targets)}.")
    else:
        lines.append(
            "You have NO specialists this turn and cannot start any research. "
            "Reply with a terminal tool only."
        )

    if phase is Phase.GREETING:
        lines.append(
            "No destination on file. If this is a greeting or small talk, call "
            "greet_and_introduce. "
            "If the user named a place, call record_trip_details "
            + (
                "then hand off to place_resolver."
                if "place_resolver" in targets
                # A bare place name matches no travel word, so this turn has no specialists.
                # Recording it is enough: the name lands on the brief, which makes the next
                # turn a planning turn and wires place_resolver then.
                else "and then ask_user for the trip length. Do not attempt a handoff."
            )
        )
    elif phase is Phase.RESOLVING:
        options = " or ".join(
            ", ".join(part for part in (c.label, c.region, c.country) if part)
            for c in brief.candidates
        )
        lines.append(
            f"The destination is ambiguous. If the user has now picked one, call "
            f"choose_candidate. Otherwise call ask_user with a question that names every "
            f"option in full - {options} - so they can tell them apart. Plan nothing yet."
        )
    elif phase is Phase.GATHERING:
        missing = missing_slots(brief)
        lines.append(
            f"Still missing: {', '.join(missing)}. Record anything the user just gave with "
            f"record_trip_details, then call ask_user for '{missing[0]}' only - one question "
            f'per turn. Ask exactly this: "{question_for(missing[0])}" '
            "If the user says they don't mind or asks you to decide, call assume_defaults instead."
        )
    elif phase is Phase.BUILDING:
        lines.append(_building_directive(brief, pending_specialists(brief)))
    elif phase is Phase.PLANNED:
        leg = primary_leg(brief)
        where = leg.label if leg else "the trip"
        lines.append(
            f"A plan for {where} was already given. Record any change with record_trip_details, "
            "re-run only the specialists whose inputs changed, and reply with the updated plan. "
            "Keep everything the user did not change."
        )

    if verdict is not None and verdict.action.value == "flag":
        lines.append(flag_note(verdict))

    return "\n".join(lines)


class DirectiveContextProvider(ContextProvider):
    """Re-renders the coordinator's next move from the live brief on every activation.

    Rendering it once per turn was a bug with a long tail: the brief changes on every hop,
    so a directive fixed at the start of the turn kept telling the coordinator to hand off
    to a specialist that had already reported back, and the two looped until the hop
    budget ran out.
    """

    def __init__(self, verdict: SafetyVerdict | None = None) -> None:
        super().__init__("trip_directive")
        self._verdict = verdict

    async def before_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
    ) -> None:
        brief = current_brief()
        directive = coordinator_directive(brief, brief.last_user_message or "", self._verdict)
        context.extend_instructions(self.source_id, directive)


__all__ = [
    "COORDINATOR_NAME",
    "SPECIALIST_ORDER",
    "SPECIALIST_SERVICES",
    "DirectiveContextProvider",
    "coordinator_directive",
    "eligible_targets",
    "is_conversational",
    "wants_surprise",
]
