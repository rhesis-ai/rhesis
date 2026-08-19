"""Tool behaviour, especially the ways they fail.

The rule under test throughout: a tool never raises, always returns a sentence the model
can repeat, and records an outage on the brief so the rest of the conversation can route
around it.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.mocks import (
    PORTLAND_ME,
    PORTLAND_OR,
    TOKYO,
    FakeHTTP,
    error,
    forecast,
    landmarks,
    nominatim,
    ok,
    osrm,
    overpass,
    timeout,
)
from travel_agent.brief import bind_brief
from travel_agent.faults import ToolFaultMiddleware
from travel_agent.state import Sight, TripBrief, TripLeg, missing_slots, needs_a_real_city
from travel_agent.tools import base
from travel_agent.tools.base import ToolStatus, parse_faults
from travel_agent.tools.dining import find_dining
from travel_agent.tools.lodging import check_lodging_budget, rates_for
from travel_agent.tools.places import resolve_destination
from travel_agent.tools.routing import estimate_travel
from travel_agent.tools.sights import find_sightseeing
from travel_agent.tools.surprise import DESTINATIONS, get_random_destination
from travel_agent.tools.weather import get_weather


async def invoke(tool, **kwargs):
    """Call a MAF ``@tool``-decorated function directly, sync or async."""
    func = tool.func if hasattr(tool, "func") else tool
    result = func(**kwargs)
    return await result if asyncio.iscoroutine(result) else result


def tokyo(**kwargs) -> TripBrief:
    return TripBrief(legs=[TripLeg(city="Tokyo", days=3, lat=35.68, lon=139.69, **kwargs)])


# region places


async def test_resolve_records_the_city_and_its_coordinates(monkeypatch):
    FakeHTTP({"places": ok(nominatim(TOKYO))}).install(monkeypatch)
    brief = TripBrief()
    with bind_brief(brief):
        await invoke(resolve_destination, place="Tokyo")
    assert brief.legs[0].city == "Tokyo"
    assert brief.legs[0].lat == pytest.approx(35.68)


async def test_same_name_rivals_become_candidates(monkeypatch):
    FakeHTTP({"places": ok(nominatim(PORTLAND_OR, PORTLAND_ME))}).install(monkeypatch)
    brief = TripBrief()
    with bind_brief(brief):
        message = await invoke(resolve_destination, place="Portland")
    assert [c.region for c in brief.candidates] == ["Oregon", "Maine"]
    assert brief.legs == [], "nothing is planned until the ambiguity is settled"
    assert "ambiguous" in message


async def test_unrelated_far_away_matches_do_not_count_as_ambiguity(monkeypatch):
    """Only rivals sharing the queried name matter; anything else would be noise."""
    other = {"name": "Tokyo Bay", "country": "Japan", "lat": 35.5, "lon": 139.8}
    FakeHTTP({"places": ok(nominatim(TOKYO, other))}).install(monkeypatch)
    brief = TripBrief()
    with bind_brief(brief):
        await invoke(resolve_destination, place="Tokyo")
    assert brief.candidates == []
    assert brief.legs[0].city == "Tokyo"


async def test_a_dead_geocoder_still_records_the_destination(monkeypatch):
    """Losing coordinates must not lose the trip."""
    FakeHTTP({"places": timeout()}).install(monkeypatch)
    brief = TripBrief()
    with bind_brief(brief):
        message = await invoke(resolve_destination, place="Kyoto")
    assert brief.legs[0].city == "Kyoto"
    assert brief.legs[0].lat is None
    assert brief.unavailable["places"] == "request timed out"
    assert "unavailable" in message


async def test_no_match_asks_the_user_rather_than_guessing(monkeypatch):
    FakeHTTP({"places": ok([])}).install(monkeypatch)
    brief = TripBrief()
    with bind_brief(brief):
        message = await invoke(resolve_destination, place="Zzzzz")
    assert brief.legs == []
    assert "No city matching" in message


# region weather, sights, dining, transit


async def test_weather_summarises_into_packing_advice(monkeypatch):
    FakeHTTP({"weather": ok(forecast([8, 9, 7], [2, 3, 1], [61, 63, 3]))}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        await invoke(get_weather, city="Tokyo")
    assert "rain on 2 of 3 days" in brief.legs[0].weather
    assert "waterproof" in brief.legs[0].weather


@pytest.mark.parametrize("failure", [timeout(), error()])
async def test_weather_failure_is_recorded_and_explained(monkeypatch, failure):
    FakeHTTP({"weather": failure}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        message = await invoke(get_weather, city="Tokyo")
    assert "weather" in brief.unavailable
    assert brief.legs[0].weather is None
    assert "unreachable" in message


async def test_missing_coordinates_degrade_rather_than_crash():
    """An un-geocoded leg is a missing precondition, not a dead service.

    Recording it as an outage used to deadlock the service: the router drops a specialist
    whose service is in ``unavailable``, so the one agent that could have cleared the entry
    by succeeding was never wired again.
    """
    brief = TripBrief(legs=[TripLeg(city="Kyoto", days=2)])
    with bind_brief(brief):
        message = await invoke(get_weather, city="Kyoto")
    assert "weather" not in brief.unavailable
    assert "weather" not in brief.no_results
    assert "could not be looked up" in message


async def test_sights_are_deduped_by_name(monkeypatch):
    """OpenStreetMap models one landmark as several elements; the user wants it listed once."""
    FakeHTTP({"sights": ok(landmarks("Senso-ji", "Senso-ji", "Tokyo Tower"))}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        await invoke(find_sightseeing, city="Tokyo")
    assert [s.name for s in brief.legs[0].sights] == ["Senso-ji", "Tokyo Tower"]


async def test_sights_take_coordinates_from_a_way_centre(monkeypatch):
    """Ways and relations carry their coordinate under ``center``, not ``lat``/``lon``."""
    payload = {
        "elements": [{"tags": {"name": "Imperial Palace"}, "center": {"lat": 35.68, "lon": 139.75}}]
    }
    FakeHTTP({"sights": ok(payload)}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        await invoke(find_sightseeing, city="Tokyo")
    sight = brief.legs[0].sights[0]
    assert (sight.lat, sight.lon) == (35.68, 139.75)


async def test_sights_are_capped_and_spread(monkeypatch):
    """Returning the eight nearest would be eight buildings on one street."""
    from travel_agent.tools.sights import MAX_SIGHTS

    FakeHTTP({"sights": ok(landmarks(*[f"Place {i}" for i in range(40)]))}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        await invoke(find_sightseeing, city="Tokyo")
    names = [s.name for s in brief.legs[0].sights]
    assert len(names) == MAX_SIGHTS
    assert names[0] == "Place 0" and names[-1] != "Place 7"


async def test_sights_respect_exclusions(monkeypatch):
    FakeHTTP({"sights": ok(landmarks("Edo Museum", "Ueno Park"))}).install(monkeypatch)
    brief = tokyo()
    brief.excluded_interests = ["museums"]
    with bind_brief(brief):
        await invoke(find_sightseeing, city="Tokyo")
    assert [s.name for s in brief.legs[0].sights] == ["Ueno Park"]


async def test_empty_dining_results_are_not_treated_as_an_outage(monkeypatch):
    FakeHTTP({"dining": ok(overpass())}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        message = await invoke(find_dining, city="Tokyo", cuisine="fondue", diet="vegan")
    assert "dining" not in brief.unavailable
    assert "genuine zero-result" in message
    assert "Do not invent venue names" in message


async def test_transit_reports_the_measured_spread(monkeypatch):
    FakeHTTP({"transit": ok(osrm(600.0, 1500.0))}).install(monkeypatch)
    brief = tokyo(
        sights=[
            Sight(name="Senso-ji", lat=35.7, lon=139.8),
            Sight(name="Tokyo Tower", lat=35.6, lon=139.7),
        ]
    )
    with bind_brief(brief):
        await invoke(estimate_travel, city="Tokyo")
    assert "10-25 minutes away" in brief.legs[0].transit
    assert "Senso-ji is closest" in brief.legs[0].transit


async def test_transit_without_sights_has_nothing_to_measure():
    brief = tokyo()
    with bind_brief(brief):
        message = await invoke(estimate_travel, city="Tokyo")
    assert "nothing to measure" in message
    assert "transit" not in brief.unavailable


# region lodging


async def test_impossible_budget_is_flagged_with_both_numbers():
    brief = TripBrief(legs=[TripLeg(city="Paris", days=2)])
    brief.budget_level = "luxury"
    with bind_brief(brief):
        message = await invoke(check_lodging_budget, city="Paris", nightly_budget_usd=20)
    assert "does not reach luxury" in brief.lodging_note
    assert "$20" in brief.lodging_note
    assert "hostel dorm bed" in brief.lodging_note
    assert "two ways forward" in message


async def test_adequate_budget_passes():
    brief = TripBrief(legs=[TripLeg(city="Paris", days=2)])
    brief.budget_level = "mid_range"
    with bind_brief(brief):
        message = await invoke(check_lodging_budget, city="Paris", nightly_budget_usd=250)
    assert "Budget check passed" in message


async def test_no_stated_budget_returns_reference_rates():
    brief = TripBrief(legs=[TripLeg(city="Paris", days=2)])
    with bind_brief(brief):
        await invoke(check_lodging_budget, city="Paris")
    assert "typical Paris nightly rates" in brief.lodging_note


def test_unknown_cities_fall_back_to_default_rates():
    assert rates_for("Paris") != rates_for("Nowheresville")
    assert rates_for("PARIS") == rates_for("paris")


# region surprise


async def test_surprise_picks_from_the_list_and_records_it():
    brief = TripBrief()
    with bind_brief(brief):
        await invoke(get_random_destination)
    assert brief.legs, "the pick must land in the brief, not just the reply text"
    assert any(brief.legs[0].city in option for option in DESTINATIONS)
    assert brief.legs[0].lat is None, "the place resolver still has to geocode it"


# region fault injection and the middleware net


def test_fault_plan_parsing():
    plan = parse_faults("weather:timeout,transit:error,sights:empty")
    assert plan.for_service("weather") is ToolStatus.TIMEOUT
    assert plan.for_service("transit") is ToolStatus.ERROR
    assert plan.for_service("sights") is ToolStatus.EMPTY
    assert plan.for_service("dining") is None


def test_fault_plan_ignores_junk():
    assert parse_faults("").faults == {}
    assert parse_faults(None).faults == {}
    assert parse_faults("weather:nonsense").faults == {}


async def test_injected_faults_short_circuit_the_request(monkeypatch):
    monkeypatch.setenv("TRAVEL_AGENT_FAULTS", "weather:timeout")
    calls: list[str] = []

    async def _never(*args, **kwargs):
        calls.append("http")
        raise AssertionError("no request should be made when a fault is forced")

    monkeypatch.setattr(base.httpx, "AsyncClient", _never)
    outcome = await base.http_get_json("weather", "https://example.invalid")
    assert outcome.status is ToolStatus.TIMEOUT
    assert calls == []


async def test_middleware_turns_a_crashing_tool_into_a_degraded_result():
    """Even a bug in a tool must not end the turn."""
    middleware = ToolFaultMiddleware()

    class Ctx:
        function = type("F", (), {"name": "get_weather"})()
        result = None

    async def boom():
        raise ValueError("kaboom")

    brief = tokyo()
    ctx = Ctx()
    with bind_brief(brief):
        await middleware.process(ctx, boom)
    assert "weather" in brief.unavailable
    assert ctx.result is not None


async def test_middleware_never_swallows_a_handoff():
    """Handoff tools are routing signals; wrapping them would break the graph."""
    middleware = ToolFaultMiddleware()
    seen: list[str] = []

    class Ctx:
        function = type("F", (), {"name": "handoff_to_trip_coordinator"})()
        result = None

    async def passthrough():
        seen.append("called")

    await middleware.process(Ctx(), passthrough)
    assert seen == ["called"]


async def test_sights_fall_back_to_wikipedia_when_overpass_is_down(monkeypatch):
    """Overpass has the better data; Wikipedia is the one that is always up."""
    calls: list[str] = []

    async def fake(service: str, url: str, **_kwargs):
        calls.append(url)
        if "overpass" in url:
            return timeout()
        return ok(
            {"query": {"geosearch": [{"title": "Pike Place Market", "lat": 47.6, "lon": -122.3}]}}
        )

    monkeypatch.setattr(base, "http_get_json", fake)
    brief = tokyo()
    with bind_brief(brief):
        message = await invoke(find_sightseeing, city="Tokyo")

    assert len(calls) == 2, "it must actually try Overpass first"
    assert [s.name for s in brief.legs[0].sights] == ["Pike Place Market"]
    assert "sights" not in brief.unavailable
    assert "Pike Place Market" in message


async def test_sights_only_degrade_when_both_sources_fail(monkeypatch):
    async def fake(service: str, url: str, **_kwargs):
        return timeout()

    monkeypatch.setattr(base, "http_get_json", fake)
    brief = tokyo()
    with bind_brief(brief):
        message = await invoke(find_sightseeing, city="Tokyo")

    assert brief.unavailable["sights"] == "request timed out"
    assert "general knowledge" in message


async def test_a_country_becomes_a_question_not_a_destination(monkeypatch):
    """ "Japan" cannot be geocoded to a point, so keeping it would break every later lookup."""
    payload = [
        {"addresstype": "country", "lat": "36.0", "lon": "138.0", "address": {"country": "Japan"}}
    ]
    FakeHTTP({"places": ok(payload)}).install(monkeypatch)
    brief = TripBrief(legs=[TripLeg(city="Japan", days=3)])

    with bind_brief(brief):
        message = await invoke(resolve_destination, place="Japan")

    # The leg stays: removing it only made the coordinator record the country again on its
    # next activation. The attempt marker is what moves the conversation on to a city.
    assert [leg.city for leg in brief.legs] == ["Japan"]
    assert brief.resolution_attempts["Japan"] == "country, not a city"
    assert "is a country, not a city" in message
    assert needs_a_real_city(brief)


# region empty results versus outages


async def test_an_empty_landmark_search_is_not_an_outage(monkeypatch):
    """A source that answers with nothing is not a source that is down.

    ``brief.unavailable`` makes the router drop the specialist for the rest of the
    conversation, which is the right response to a dead API and the wrong one to a city
    Overpass simply has no tagged attractions for.
    """
    FakeHTTP({"sights": ok({"elements": []})}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        message = await invoke(find_sightseeing, city="Tokyo")

    assert "sights" not in brief.unavailable
    assert brief.no_results["sights"] == "no landmarks found"
    assert "came back empty" in message


async def test_sights_excluded_to_nothing_is_not_an_outage(monkeypatch):
    """Everything found was ruled out by the user, which says nothing about the service."""
    FakeHTTP({"sights": ok(landmarks("Tokyo National Museum"))}).install(monkeypatch)
    brief = tokyo()
    brief.excluded_interests = ["museum"]
    with bind_brief(brief):
        await invoke(find_sightseeing, city="Tokyo")

    assert "sights" not in brief.unavailable
    assert "sights" in brief.no_results


async def test_no_usable_route_is_not_an_outage(monkeypatch):
    """OSRM answered; it just could not route between these points."""
    FakeHTTP({"transit": ok({"durations": [[0]]})}).install(monkeypatch)
    brief = tokyo(sights=[Sight(name="Senso-ji", lat=35.71, lon=139.79)])
    with bind_brief(brief):
        message = await invoke(estimate_travel, city="Tokyo")

    assert "transit" not in brief.unavailable
    assert brief.no_results["transit"] == "no route found"
    assert "no usable route" in message


async def test_an_empty_restaurant_search_is_not_an_outage(monkeypatch):
    FakeHTTP({"dining": ok({"elements": []})}).install(monkeypatch)
    brief = tokyo()
    with bind_brief(brief):
        message = await invoke(find_dining, city="Tokyo", cuisine="Ethiopian")

    assert "dining" not in brief.unavailable
    assert "dining" in brief.no_results
    assert "genuine zero-result" in message


async def test_a_later_success_clears_a_past_empty_result(monkeypatch):
    brief = tokyo()
    FakeHTTP({"sights": ok({"elements": []})}).install(monkeypatch)
    with bind_brief(brief):
        await invoke(find_sightseeing, city="Tokyo")
    assert "sights" in brief.no_results

    FakeHTTP({"sights": ok(overpass("Senso-ji"))}).install(monkeypatch)
    with bind_brief(brief):
        await invoke(find_sightseeing, city="Tokyo")
    assert "sights" not in brief.no_results


async def test_a_geocoder_outage_does_not_strand_the_destination(monkeypatch):
    """A dead Nominatim costs coordinates for the session; it must not cost the destination."""
    FakeHTTP({"places": timeout()}).install(monkeypatch)
    brief = TripBrief()
    with bind_brief(brief):
        message = await invoke(resolve_destination, place="Paris")

    assert brief.resolution_attempts["Paris"] == "timeout"
    assert brief.unavailable["places"] == "request timed out"
    assert [leg.city for leg in brief.legs] == ["Paris"]
    # The name is still good, so the conversation carries on instead of asking which city.
    assert not needs_a_real_city(brief)
    assert "city" not in missing_slots(brief)
    assert "without map coordinates" in message
