"""Conversation storage and the turn wrapper."""

from __future__ import annotations

import asyncio

from tests.mocks import call, client_for, text
from travel_agent.session import StateStore, run_chat_turn, run_chat_turn_sync
from travel_agent.state import TripBrief, TripLeg
from travel_agent.terminals import GREETING


def greeting_script():
    return [call("greet_and_introduce"), text("done")]


def test_snapshot_of_an_unknown_conversation_is_empty():
    brief, messages = StateStore().snapshot("nope")
    assert brief.legs == []
    assert messages == []


def test_snapshots_are_copies_so_a_failed_turn_cannot_corrupt_the_store():
    store = StateStore()
    store.save("c1", TripBrief(legs=[TripLeg(city="Tokyo", days=3)]), [])

    brief, _ = store.snapshot("c1")
    brief.legs[0].city = "Corrupted"

    again, _ = store.snapshot("c1")
    assert again.legs[0].city == "Tokyo"


def test_messages_are_trimmed_to_the_cap():
    store = StateStore(max_messages_per_conversation=3)
    from travel_agent.utils import user_message

    store.save("c1", TripBrief(), [user_message(str(i)) for i in range(10)])
    assert [m.text for m in store.get_messages("c1")] == ["7", "8", "9"]


def test_oldest_conversation_is_evicted_at_the_cap():
    store = StateStore(max_conversations=2)
    for name in ("a", "b", "c"):
        store.save(name, TripBrief(), [])
    assert "a" not in store.list_conversations()
    assert set(store.list_conversations()) == {"b", "c"}


def test_delete_reports_whether_it_existed():
    store = StateStore()
    store.save("c1", TripBrief(), [])
    assert store.delete("c1") is True
    assert store.delete("c1") is False


async def test_run_chat_turn_persists_the_brief_and_transcript():
    store = StateStore()
    result = await run_chat_turn(
        "Hi", conversation_id="c1", store=store, client=client_for(*greeting_script())
    )

    assert result["response"] == GREETING
    assert result["conversation_id"] == "c1"
    assert store.get_brief("c1").turn == 1
    assert [m.role for m in store.get_messages("c1")] == ["user", "assistant"]


async def test_run_chat_turn_mints_an_id_when_none_is_given():
    store = StateStore()
    result = await run_chat_turn("Hi", store=store, client=client_for(*greeting_script()))
    assert result["conversation_id"]
    assert result["conversation_id"] in store.list_conversations()


async def test_state_carries_across_turns():
    store = StateStore()
    await run_chat_turn(
        "I want to go to Tokyo",
        conversation_id="c1",
        store=store,
        client=client_for(
            call("record_trip_details", destination="Tokyo", days=3),
            call("ask_user", question="What interests you?"),
            text("done"),
        ),
    )
    result = await run_chat_turn(
        "ok",
        conversation_id="c1",
        store=store,
        client=client_for(call("ask_user", question="Budget?"), text("done")),
    )

    brief = store.get_brief("c1")
    assert brief.legs[0].city == "Tokyo"
    assert brief.legs[0].days == 3
    assert brief.turn == 2
    assert len(result["messages"]) == 4


async def test_conversations_do_not_leak_into_each_other():
    store = StateStore()
    await run_chat_turn(
        "Tokyo please",
        conversation_id="a",
        store=store,
        client=client_for(
            call("record_trip_details", destination="Tokyo", days=3),
            call("ask_user", question="Interests?"),
            text("done"),
        ),
    )
    await run_chat_turn(
        "Hi", conversation_id="b", store=store, client=client_for(*greeting_script())
    )

    assert store.get_brief("a").legs[0].city == "Tokyo"
    assert store.get_brief("b").legs == []


async def test_turns_in_one_conversation_are_serialised():
    """Concurrent turns must not interleave and lose an update."""
    store = StateStore()

    async def one(city: str):
        return await run_chat_turn(
            f"go to {city}",
            conversation_id="shared",
            store=store,
            client=client_for(
                call("record_trip_details", destination=city, days=2),
                call("ask_user", question="Interests?"),
                text("done"),
            ),
        )

    await asyncio.gather(one("Tokyo"), one("Osaka"))

    brief = store.get_brief("shared")
    assert brief.turn == 2, "both turns must be counted"
    assert len(brief.legs) == 1


def test_turn_lock_is_rebuilt_when_the_event_loop_changes():
    """The connector runs each turn on a fresh loop; a stale lock would raise on contention."""
    store = StateStore()

    def in_new_loop():
        return asyncio.run(
            run_chat_turn(
                "Hi", conversation_id="c1", store=store, client=client_for(*greeting_script())
            )
        )

    assert in_new_loop()["response"] == GREETING
    assert in_new_loop()["response"] == GREETING
    assert store.get_brief("c1").turn == 2


def test_sync_wrapper_runs_outside_a_loop():
    store = StateStore()
    result = run_chat_turn_sync(
        "Hi", conversation_id="c1", store=store, client=client_for(*greeting_script())
    )
    assert result["response"] == GREETING


async def test_sync_wrapper_refuses_to_run_inside_a_loop():
    import pytest

    with pytest.raises(RuntimeError, match="cannot be called from an active event loop"):
        run_chat_turn_sync("Hi", client=client_for(*greeting_script()))
