"""The trip brief: the rules that make memory survive a sloppy turn."""

from __future__ import annotations

import pytest

from travel_agent.state import (
    Phase,
    PlaceCandidate,
    Sight,
    TripBrief,
    TripLeg,
    add_interests,
    clear_unavailable,
    derive_phase,
    exclude_interests,
    find_leg,
    mark_unavailable,
    missing_slots,
    needs_a_real_city,
    pending_specialists,
    render_brief,
    render_plan,
    set_destination,
    wants_food,
)


def tokyo(**kwargs) -> TripBrief:
    return TripBrief(legs=[TripLeg(city="Tokyo", days=3, lat=35.68, lon=139.69, **kwargs)])


# region destinations


def test_set_destination_replaces_the_trip_but_keeps_the_duration():
    """A pivot changes the city, not the timeframe - the user should not restate it."""
    brief = tokyo()
    set_destination(brief, "Kyoto")
    assert [leg.city for leg in brief.legs] == ["Kyoto"]
    assert brief.legs[0].days == 3


def test_additional_stop_appends_a_leg():
    brief = TripBrief(legs=[TripLeg(city="London", days=3)])
    set_destination(brief, "Paris", days=2, replace=False)
    assert [(leg.city, leg.days) for leg in brief.legs] == [("London", 3), ("Paris", 2)]


def test_set_destination_on_a_known_city_updates_it_in_place():
    brief = tokyo()
    set_destination(brief, "Tokyo", days=5)
    assert len(brief.legs) == 1
    assert brief.legs[0].days == 5


def test_setting_a_destination_clears_pending_candidates():
    brief = TripBrief(candidates=[PlaceCandidate(label="Portland", region="Oregon")])
    set_destination(brief, "Portland", region="Oregon")
    assert brief.candidates == []


def test_blank_destination_is_rejected():
    with pytest.raises(ValueError):
        set_destination(TripBrief(), "   ")


def test_find_leg_is_case_insensitive():
    assert find_leg(tokyo(), "tokyo") is not None
    assert find_leg(tokyo(), "Osaka") is None


# region interests


def test_interests_are_deduped_and_blanks_dropped():
    brief = tokyo()
    add_interests(brief, ["food", " food ", "", "Art"])
    assert brief.legs[0].interests == ["food", "Art"]


def test_excluded_interests_are_never_re_added():
    brief = tokyo()
    exclude_interests(brief, ["museums"])
    add_interests(brief, ["museums", "food"])
    assert brief.legs[0].interests == ["food"]


def test_exclusion_purges_matching_sights_including_plurals():
    brief = tokyo(sights=[Sight(name="Museum of Fine Arts"), Sight(name="Prater Park")])
    exclude_interests(brief, ["museums"])
    assert [s.name for s in brief.legs[0].sights] == ["Prater Park"]


def test_short_exclusions_do_not_match_everything():
    """A three-letter term would match half the sights in any city."""
    brief = tokyo(sights=[Sight(name="Art Museum"), Sight(name="Park")])
    exclude_interests(brief, ["zoo"])
    assert len(brief.legs[0].sights) == 2


def test_wants_food_reads_interests():
    assert wants_food(tokyo(interests=["hidden foodie spots"]))
    assert not wants_food(tokyo(interests=["architecture"]))


# region phase


def test_phase_is_derived_from_the_brief():
    assert derive_phase(TripBrief()) is Phase.GREETING
    assert derive_phase(TripBrief(legs=[TripLeg(city="Tokyo")])) is Phase.GATHERING
    assert derive_phase(tokyo()) is Phase.BUILDING

    planned = tokyo()
    planned.plan_text = "here is your plan"
    assert derive_phase(planned) is Phase.PLANNED


def test_ambiguity_outranks_every_other_phase():
    """Planning against the wrong Portland is worse than planning nothing."""
    brief = tokyo()
    brief.plan_text = "a plan"
    brief.candidates = [PlaceCandidate(label="Portland", region="Oregon")]
    assert derive_phase(brief) is Phase.RESOLVING


def test_missing_slots_orders_blocking_ones_first():
    assert missing_slots(TripBrief()) == ["destination"]
    assert missing_slots(TripBrief(legs=[TripLeg(city="Tokyo")]))[0] == "duration"
    assert missing_slots(tokyo()) == ["interests", "budget"]


# region specialist scheduling


def test_pending_specialists_respects_dependencies():
    """Transit routes between sights, so it cannot be pending before they exist."""
    brief = tokyo()
    assert "sightseeing_scout" in pending_specialists(brief)
    assert "transit_planner" not in pending_specialists(brief)

    brief.legs[0].sights = [Sight(name="Senso-ji", lat=35.7, lon=139.8)]
    assert "transit_planner" in pending_specialists(brief)


def test_dining_is_only_scheduled_when_food_was_mentioned():
    assert "dining_scout" not in pending_specialists(tokyo())
    assert "dining_scout" in pending_specialists(tokyo(interests=["street food"]))


def test_lodging_is_only_scheduled_once_a_budget_exists():
    brief = tokyo()
    assert "lodging_advisor" not in pending_specialists(brief)
    brief.budget_level = "mid_range"
    assert "lodging_advisor" in pending_specialists(brief)


def test_a_downed_service_stops_costing_a_hop():
    brief = tokyo()
    mark_unavailable(brief, "sights", "request timed out")
    assert "sightseeing_scout" not in pending_specialists(brief)
    clear_unavailable(brief, "sights")
    assert "sightseeing_scout" in pending_specialists(brief)


# region rendering


def test_render_brief_states_emptiness_plainly():
    rendered = render_brief(TripBrief())
    assert "Nothing on file yet" in rendered
    assert "Phase: greeting" in rendered
    assert "Still needed: destination" in rendered


def test_render_brief_surfaces_outages_with_an_instruction():
    brief = tokyo()
    mark_unavailable(brief, "weather", "request timed out")
    rendered = render_brief(brief)
    assert "weather (request timed out)" in rendered
    assert "never invent it" in rendered.lower()


def test_render_brief_lists_every_leg_of_a_multi_city_trip():
    brief = TripBrief(legs=[TripLeg(city="London", days=3), TripLeg(city="Paris", days=2)])
    rendered = render_brief(brief)
    assert "Stop 1: London (3 days)" in rendered
    assert "Stop 2: Paris (2 days)" in rendered


def test_render_plan_uses_only_what_the_brief_holds():
    brief = tokyo(sights=[Sight(name="Senso-ji")], weather="highs around 20C")
    mark_unavailable(brief, "transit", "request timed out")
    plan = render_plan(brief)
    assert "Senso-ji" in plan
    assert "highs around 20C" in plan
    assert "couldn't reach the transit service" in plan


def test_render_plan_without_a_destination_asks_for_one():
    assert "don't have a destination" in render_plan(TripBrief())


def test_an_unplannable_destination_goes_back_to_asking():
    """A country or a typo cannot be geocoded, so building around it is worse than asking."""
    brief = TripBrief(legs=[TripLeg(city="Japan", days=3)])
    assert derive_phase(brief) is Phase.BUILDING, "before the geocoder runs it looks plannable"

    brief.resolution_attempts["Japan"] = "country, not a city"
    assert needs_a_real_city(brief)
    assert derive_phase(brief) is Phase.GATHERING
    assert missing_slots(brief) == ["city"], "nothing else matters until it can be placed"


def test_a_placed_destination_does_not_need_narrowing():
    brief = tokyo()
    brief.resolution_attempts["Tokyo"] = "ok"
    assert not needs_a_real_city(brief)
    assert derive_phase(brief) is Phase.BUILDING
