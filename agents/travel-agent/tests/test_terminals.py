"""Coordinator state and terminal tools, exercised directly against a bound brief."""

from __future__ import annotations

import pytest

from travel_agent.brief import bind_brief, current_brief
from travel_agent.state import Sight, TripBrief, TripLeg, pending_specialists
from travel_agent.terminals import (
    GREETING,
    TERMINAL_TOOLS,
    assume_defaults,
    greet_and_introduce,
    record_trip_details,
    redirect_to_scope,
)


@pytest.fixture
def brief():
    trip = TripBrief()
    with bind_brief(trip):
        yield trip


def invoke(tool, **kwargs):
    """Call a MAF ``@tool``-decorated function directly."""
    return tool.func(**kwargs) if hasattr(tool, "func") else tool(**kwargs)


def test_tools_require_a_bound_brief():
    with pytest.raises(RuntimeError, match="No trip brief is bound"):
        current_brief()


def test_greeting_sets_the_reply_and_names_the_capabilities(brief):
    invoke(greet_and_introduce)
    assert brief.pending_reply == GREETING
    for capability in ("itinerar", "weather", "travel times", "budget"):
        assert capability in GREETING.lower()


def test_greeting_is_listed_as_terminal():
    assert "greet_and_introduce" in TERMINAL_TOOLS
    assert "redirect_to_scope" in TERMINAL_TOOLS
    assert "ask_user" in TERMINAL_TOOLS


def test_redirect_declines_and_refuses_role_play(brief):
    invoke(redirect_to_scope, topic="sports trivia")
    assert "can't help with sports trivia" in brief.pending_reply
    assert "another role" in brief.pending_reply


def test_redirect_falls_back_to_the_next_question_when_no_follow_up_given(brief):
    invoke(redirect_to_scope, topic="coding")
    assert "Where would you like to go" in brief.pending_reply


def test_redirect_returns_to_the_trip_on_file():
    trip = TripBrief(legs=[TripLeg(city="Tokyo", days=3)])
    with bind_brief(trip):
        invoke(redirect_to_scope, topic="sports trivia")
    assert "Back to your 3-day trip to Tokyo" in trip.pending_reply


def test_record_trip_details_fills_slots(brief):
    invoke(
        record_trip_details,
        destination="Tokyo",
        days=3,
        interests="food, modern art",
        budget_level="mid-range",
    )
    assert brief.legs[0].city == "Tokyo"
    assert brief.legs[0].days == 3
    assert brief.legs[0].interests == ["food", "modern art"]
    assert brief.budget_level == "mid_range"


def test_record_trip_details_ignores_blanks_so_a_slot_cannot_be_erased():
    trip = TripBrief(legs=[TripLeg(city="Tokyo", days=3, interests=["food"])])
    trip.budget_level = "luxury"
    with bind_brief(trip):
        invoke(record_trip_details, destination="", days=0, interests="", budget_level="")
    assert trip.legs[0].city == "Tokyo"
    assert trip.legs[0].days == 3
    assert trip.legs[0].interests == ["food"]
    assert trip.budget_level == "luxury"


def test_recording_days_alone_updates_the_current_leg():
    trip = TripBrief(legs=[TripLeg(city="Chicago")])
    with bind_brief(trip):
        invoke(record_trip_details, days=4)
    assert trip.legs[0].days == 4


def test_dislikes_invalidate_a_previous_plan():
    trip = TripBrief(legs=[TripLeg(city="Vienna", days=3, sights=[Sight(name="Art Museum")])])
    trip.plan_text = "an itinerary the user hated"
    with bind_brief(trip):
        invoke(record_trip_details, dislikes="museums")
    assert trip.plan_text is None
    assert trip.legs[0].sights == []


def test_assume_defaults_fills_everything_planning_needs(brief):
    brief.legs.append(TripLeg(city="Seattle"))
    result = invoke(assume_defaults)
    assert brief.budget_level == "mid_range"
    assert brief.legs[0].days == 3
    assert brief.legs[0].interests == ["popular highlights"]
    assert "Say plainly in the plan that you assumed this" in result


def test_assume_defaults_is_a_no_op_when_nothing_is_missing():
    trip = TripBrief(legs=[TripLeg(city="Seattle", days=3, interests=["food"])])
    trip.budget_level = "budget"
    with bind_brief(trip):
        assert "Nothing left to assume" in invoke(assume_defaults)


def test_a_changed_budget_makes_the_lodging_note_stale():
    """The note is derived from the tier, so a new tier has to re-run lodging_advisor.

    Leaving it in place made a refinement turn depend on the coordinator noticing, which is
    exactly the kind of judgement a small model does not reliably make.
    """
    trip = TripBrief(legs=[TripLeg(city="Tokyo", days=3, lat=35.68, lon=139.69)])
    trip.budget_level = "budget"
    trip.lodging_note = "Around 60 EUR a night."
    trip.plan_text = "your plan"

    with bind_brief(trip):
        invoke(record_trip_details, budget_level="luxury")

    assert trip.budget_level == "luxury"
    assert trip.lodging_note is None
    assert trip.plan_text is None
    assert "lodging_advisor" in pending_specialists(trip)


def test_restating_the_same_budget_changes_nothing():
    trip = TripBrief(legs=[TripLeg(city="Tokyo", days=3)])
    trip.budget_level = "budget"
    trip.lodging_note = "Around 60 EUR a night."
    trip.plan_text = "your plan"

    with bind_brief(trip):
        invoke(record_trip_details, budget_level="budget")

    assert trip.lodging_note == "Around 60 EUR a night."
    assert trip.plan_text == "your plan"


def test_new_interests_make_an_existing_plan_stale():
    trip = TripBrief(legs=[TripLeg(city="Tokyo", days=3)])
    trip.plan_text = "your plan"

    with bind_brief(trip):
        invoke(record_trip_details, interests="street food")

    assert trip.plan_text is None
