"""Coordinator tools that record state or end the turn with a fixed reply.

A terminal tool writes ``brief.pending_reply`` and that string *is* what the user sees.
That matters on a small model: greeting, refusing and asking a follow-up are the turns
where a free-running LLM is most likely to invent a trip nobody asked for, so those
replies are assembled in Python instead of being requested in a prompt.
"""

from __future__ import annotations

from typing import Annotated

from agent_framework import tool
from pydantic import Field

from travel_agent.brief import current_brief
from travel_agent.state import (
    BUDGET_LABELS,
    TripBrief,
    add_interests,
    exclude_interests,
    is_blank,
    missing_slots,
    primary_leg,
    render_brief,
    set_destination,
)

# Tools that end the turn. The runner serves their reply verbatim.
TERMINAL_TOOLS: tuple[str, ...] = ("greet_and_introduce", "redirect_to_scope", "ask_user")

GREETING = (
    "Hello! I'm your travel assistant. I can help you research destinations, build day-by-day "
    "itineraries, check the weather, estimate travel times between sights, and sanity-check "
    "your budget. Where are you planning to go - or would you like me to surprise you?"
)

_SLOT_QUESTIONS: dict[str, str] = {
    "destination": "Where would you like to go? I can also pick a surprise destination for you.",
    "city": "Which city would you like to visit? I plan around a single city at a time.",
    "duration": "How many days are you planning to stay?",
    "interests": "What are you most interested in - food, history, art, nightlife, nature?",
    "budget": "What budget level should I target: budget, mid-range, or luxury?",
}


def question_for(slot: str) -> str:
    """The canonical wording for a slot question, so the directive can name it exactly."""
    return _SLOT_QUESTIONS.get(slot, "What else can you tell me about your trip?")


def _next_question(brief: TripBrief) -> str:
    """The single most useful thing to ask next, or a nudge when nothing is missing."""
    missing = missing_slots(brief)
    if not missing:
        return "Shall I put the itinerary together?"
    return _SLOT_QUESTIONS[missing[0]]


def _trip_focus(brief: TripBrief) -> str:
    """A short 'back to your trip' phrase, used when steering away from an off-topic turn."""
    leg = primary_leg(brief)
    if leg is None:
        return ""
    duration = f"{leg.days}-day " if leg.days else ""
    return f"Back to your {duration}trip to {leg.label}: "


def _end_turn(brief: TripBrief, reply: str) -> str:
    brief.pending_reply = reply
    return "Replied to the user. The turn is over - do not write anything further."


@tool
def greet_and_introduce() -> str:
    """Greet the user and explain what this assistant can do. Use for greetings and small talk."""
    return _end_turn(current_brief(), GREETING)


@tool
def redirect_to_scope(
    topic: Annotated[
        str,
        Field(description="What the user asked for that is out of scope, e.g. 'sports trivia'."),
    ],
    follow_up: Annotated[
        str,
        Field(
            description=(
                "Optional travel-planning sentence to continue with, referring to the trip "
                "already on file. Leave empty to use the default."
            )
        ),
    ] = "",
) -> str:
    """Decline an out-of-scope request and steer back to travel planning."""
    brief = current_brief()
    subject = topic.strip() or "that"
    tail = follow_up.strip() or f"{_trip_focus(brief)}{_next_question(brief)}"
    reply = (
        f"I'm a travel planning assistant, so I can't help with {subject} - "
        f"and I can't share my internal configuration or take on another role. {tail}"
    )
    return _end_turn(brief, reply)


@tool
def ask_user(
    question: Annotated[
        str,
        Field(description="The single question to put to the user, phrased naturally."),
    ],
    preamble: Annotated[
        str,
        Field(
            description="Optional sentence before the question, e.g. acknowledging their answer."
        ),
    ] = "",
) -> str:
    """Ask the user one follow-up question and end the turn."""
    brief = current_brief()
    text = question.strip() or _next_question(brief)
    reply = f"{preamble.strip()} {text}".strip() if preamble.strip() else text
    return _end_turn(brief, reply)


@tool
def record_trip_details(
    destination: Annotated[
        str, Field(description="City the user named. Leave empty if they did not name one.")
    ] = "",
    days: Annotated[
        int, Field(description="Trip length in days. Use 0 when the user has not said.")
    ] = 0,
    interests: Annotated[
        str, Field(description="Comma-separated interests the user mentioned.")
    ] = "",
    budget_level: Annotated[
        str, Field(description="One of: budget, mid_range, luxury. Empty if not stated.")
    ] = "",
    dislikes: Annotated[
        str, Field(description="Comma-separated things the user does not want, e.g. 'museums'.")
    ] = "",
    additional_stop: Annotated[
        bool,
        Field(
            description=(
                "True when this destination is another stop on the same trip, not a change of plan."
            )
        ),
    ] = False,
) -> str:
    """Record what the user just told us about their trip. Call this before anything else."""
    brief = current_brief()

    if not is_blank(destination):
        set_destination(
            brief,
            destination.strip(),
            days=days or None,
            replace=not additional_stop,
        )
    elif days and (leg := primary_leg(brief)) is not None:
        leg.days = days

    if not is_blank(dislikes):
        exclude_interests(brief, [item for item in dislikes.split(",")])
    if not is_blank(interests):
        add_interests(
            brief,
            [item for item in interests.split(",")],
            city=destination.strip() if not is_blank(destination) else None,
        )

    tier = budget_level.strip().casefold().replace("-", "_").replace(" ", "_")
    changed_budget = tier in BUDGET_LABELS and tier != brief.budget_level
    if changed_budget:
        brief.budget_level = tier  # type: ignore[assignment]
        # The note is derived from the tier, so a new tier makes it stale. Clearing it is what
        # puts lodging_advisor back on ``pending_specialists`` instead of leaving the re-run to
        # the coordinator's judgement.
        brief.lodging_note = None

    # A rejected itinerary is stale the moment preferences change.
    if (
        changed_budget
        or not is_blank(dislikes)
        or not is_blank(destination)
        or not is_blank(interests)
    ):
        brief.plan_text = None

    return render_brief(brief)


@tool
def assume_defaults() -> str:
    """Fill in sensible defaults when the user says they don't mind or asks you to decide."""
    brief = current_brief()
    assumed: list[str] = []
    if brief.budget_level is None:
        brief.budget_level = "mid_range"
        assumed.append("mid-range budget")
    leg = primary_leg(brief)
    if leg is not None and not leg.interests:
        add_interests(brief, ["popular highlights"])
        assumed.append("popular, accessible highlights")
    if leg is not None and leg.days is None:
        leg.days = 3
        assumed.append("a 3-day trip")

    if not assumed:
        return "Nothing left to assume; everything needed is already on file."
    return (
        f"Assumed {', '.join(assumed)}. Say plainly in the plan that you assumed this, "
        "then continue without asking again."
    )


COORDINATOR_STATE_TOOLS = [record_trip_details, assume_defaults]
COORDINATOR_TERMINAL_TOOLS = [greet_and_introduce, redirect_to_scope, ask_user]

__all__ = [
    "COORDINATOR_STATE_TOOLS",
    "COORDINATOR_TERMINAL_TOOLS",
    "GREETING",
    "TERMINAL_TOOLS",
    "ask_user",
    "assume_defaults",
    "greet_and_introduce",
    "question_for",
    "record_trip_details",
    "redirect_to_scope",
]
