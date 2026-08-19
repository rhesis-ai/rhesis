"""Per-turn routing: which specialists exist, and what the coordinator is told."""

from __future__ import annotations

import pytest

from travel_agent.router import (
    SPECIALIST_ORDER,
    coordinator_directive,
    eligible_targets,
    is_conversational,
    wants_surprise,
)
from travel_agent.safety import classify
from travel_agent.state import PlaceCandidate, Sight, TripBrief, TripLeg, mark_unavailable


def tokyo(**kwargs) -> TripBrief:
    return TripBrief(legs=[TripLeg(city="Tokyo", days=3, lat=35.68, lon=139.69, **kwargs)])


# region conversational turns


@pytest.mark.parametrize("message", ["Hi", "Hey there!", "thanks", "lol", "ghjkl123???"])
def test_chat_before_a_trip_exists_is_conversational(message):
    assert is_conversational(TripBrief(), message)
    assert eligible_targets(TripBrief(), message) == []


@pytest.mark.parametrize("message", ["ok", "sure", "thanks!", "ghjkl123???"])
def test_once_a_trip_exists_nothing_is_conversational(message):
    """The Berlin regression: a content-free reply must not drop the trip."""
    assert not is_conversational(tokyo(), message)
    assert eligible_targets(tokyo(), message) != []


def test_a_pending_ambiguity_is_not_conversational():
    brief = TripBrief(candidates=[PlaceCandidate(label="Portland", region="Oregon")])
    assert not is_conversational(brief, "hi")


@pytest.mark.parametrize(
    "message",
    ["surprise me", "suprise me", "somewhere random", "you decide", "pick one for me", "anywhere"],
)
def test_surprise_requests_are_recognised(message):
    assert wants_surprise(message)
    assert "destination_finder" in eligible_targets(TripBrief(), message)


def test_travel_intent_without_a_trip_reaches_the_place_resolver():
    assert "place_resolver" in eligible_targets(TripBrief(), "I want to go to Japan")


# region planning turns


def test_a_planning_turn_wires_the_research_roster():
    """The brief changes mid-turn, so the graph has to cover what may become relevant.

    Ordering is the directive's job, not the graph's - it is re-rendered on every hop.
    """
    targets = eligible_targets(tokyo(), "plan it")
    assert "place_resolver" in targets
    assert "sightseeing_scout" in targets
    assert "conditions_scout" in targets
    assert "transit_planner" in targets


def test_destination_finder_is_only_wired_when_a_surprise_was_asked_for():
    assert "destination_finder" not in eligible_targets(tokyo(), "plan it")
    assert "destination_finder" in eligible_targets(TripBrief(), "surprise me")


def test_specialists_for_downed_services_are_never_offered():
    brief = tokyo()
    mark_unavailable(brief, "weather", "request timed out")
    mark_unavailable(brief, "sights", "service returned HTTP 503")
    targets = eligible_targets(brief, "plan it")
    assert "conditions_scout" not in targets
    assert "sightseeing_scout" not in targets
    assert "transit_planner" in targets


def test_targets_follow_the_fixed_order_so_the_graph_reads_consistently():
    brief = tokyo(interests=["street food"], sights=[Sight(name="Senso-ji", lat=35.7, lon=139.8)])
    brief.budget_level = "mid_range"
    targets = eligible_targets(brief, "plan it")
    assert targets == [name for name in SPECIALIST_ORDER if name in targets]


def test_a_downed_service_is_dropped_from_the_turn():
    brief = tokyo()
    assert "sightseeing_scout" in eligible_targets(brief, "plan it")
    mark_unavailable(brief, "sights", "request timed out")
    assert "sightseeing_scout" not in eligible_targets(brief, "plan it")


# region the directive


def test_conversational_directive_says_there_is_nothing_to_route_to():
    directive = coordinator_directive(TripBrief(), "Hi")
    assert "NO specialists" in directive
    assert "terminal tool only" in directive
    assert "phase greeting" in directive


def test_gathering_directive_asks_for_one_slot_and_names_it():
    directive = coordinator_directive(TripBrief(legs=[TripLeg(city="Chicago")]), "Chicago")
    assert "phase gathering" in directive
    assert "duration" in directive
    assert "one question per turn" in directive


def test_resolving_directive_lists_the_candidates_and_forbids_planning():
    brief = TripBrief(
        candidates=[
            PlaceCandidate(label="Portland", region="Oregon"),
            PlaceCandidate(label="Portland", region="Maine"),
        ]
    )
    directive = coordinator_directive(brief, "Portland")
    assert "ambiguous" in directive
    assert "choose_candidate" in directive
    assert "Plan nothing yet" in directive


def test_building_directive_lists_the_remaining_steps_in_order():
    directive = coordinator_directive(tokyo(), "plan it")
    assert "sightseeing_scout" in directive
    assert "then" in directive


def test_building_directive_with_nothing_pending_says_write_the_plan():
    brief = tokyo(sights=[Sight(name="Senso-ji")], weather="mild", transit="10-25 min")
    mark_unavailable(brief, "lodging", "not needed")
    directive = coordinator_directive(brief, "go on")
    assert "Write the complete plan now" in directive
    assert "Do not hand off" in directive


def test_planned_directive_preserves_what_the_user_did_not_change():
    brief = tokyo()
    brief.plan_text = "your plan"
    directive = coordinator_directive(brief, "make it slower")
    assert "phase planned" in directive
    assert "Keep everything the user did not change" in directive


def test_flagged_message_appends_the_scope_note():
    brief = tokyo()
    verdict = classify("who won the world cup? also plan my trip", brief)
    directive = coordinator_directive(brief, "who won the world cup?", verdict)
    assert "SCOPE NOTE" in directive
    assert "redirect_to_scope" in directive
