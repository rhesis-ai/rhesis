"""Conversation store and turn entry points."""

from __future__ import annotations

import pytest

from reg_advisor.runner import build_coordinator_agent
from reg_advisor.session import StateStore, build_turn_runner, run_chat_turn, run_chat_turn_async
from reg_advisor.state import Phase, RegAdvisorState
from tests.mocks import MockLlm, greeting_script, make_runner


def store() -> StateStore:
    return StateStore()


# --- the store ------------------------------------------------------------------------------


def test_an_unknown_conversation_returns_a_fresh_state() -> None:
    assert store().get("never-seen") == RegAdvisorState()


def test_get_and_set_both_copy_the_state() -> None:
    """Aliasing would let a caller mutate stored state without going through set()."""
    active = store()
    original = RegAdvisorState(turn=1)
    active.set("c1", original)

    original.turn = 99
    assert active.get("c1").turn == 1

    fetched = active.get("c1")
    fetched.turn = 42
    assert active.get("c1").turn == 1


def test_list_conversations_maps_id_to_turn() -> None:
    active = store()
    active.set("a", RegAdvisorState(turn=2))
    active.set("b", RegAdvisorState(turn=5))
    assert active.list_conversations() == {"a": 2, "b": 5}


def test_delete_reports_whether_anything_was_there() -> None:
    active = store()
    active.set("a", RegAdvisorState())
    assert active.delete("a") is True
    assert active.delete("a") is False
    assert active.list_conversations() == {}


def test_eviction_drops_the_oldest_conversation() -> None:
    active = StateStore(max_conversations=3)
    for name in ("a", "b", "c"):
        active.set(name, RegAdvisorState())
    active.set("d", RegAdvisorState())

    assert sorted(active.list_conversations()) == ["b", "c", "d"]


def test_eviction_only_runs_when_inserting_a_new_id() -> None:
    active = StateStore(max_conversations=2)
    active.set("a", RegAdvisorState())
    active.set("b", RegAdvisorState())
    active.set("a", RegAdvisorState(turn=9))

    assert sorted(active.list_conversations()) == ["a", "b"]
    assert active.get("a").turn == 9


def test_eviction_forgets_the_locks_too() -> None:
    active = StateStore(max_conversations=2)
    active.conversation_lock("a")
    active.async_conversation_lock("a")
    active.set("a", RegAdvisorState())
    active.set("b", RegAdvisorState())
    active.set("c", RegAdvisorState())

    assert "a" not in active._conversation_locks
    assert "a" not in active._async_locks


def test_the_same_lock_object_comes_back_for_one_conversation() -> None:
    """Two callers must contend on one lock, not on two copies of it."""
    active = store()
    assert active.conversation_lock("a") is active.conversation_lock("a")
    assert active.async_conversation_lock("a") is active.async_conversation_lock("a")
    assert active.conversation_lock("a") is not active.conversation_lock("b")


def test_the_sync_and_async_locks_are_different_objects() -> None:
    """They cannot be shared: a threading.Lock held across an await hangs the event loop."""
    active = store()
    assert active.conversation_lock("a") is not active.async_conversation_lock("a")


# --- the turn entry points ---------------------------------------------------------------------


def test_state_carries_across_turns_on_one_conversation() -> None:
    active = store()
    first = run_chat_turn("hello", store=active, runner=make_runner(greeting_script()))
    conv_id = first["conversation_id"]

    second = run_chat_turn(
        "hello again",
        conversation_id=conv_id,
        store=active,
        runner=make_runner(greeting_script()),
    )

    assert second["conversation_id"] == conv_id
    assert second["state"].turn == 2
    assert len(second["state"].history) == 4
    assert active.get(conv_id).turn == 2


def test_a_conversation_id_is_minted_when_none_is_given() -> None:
    result = run_chat_turn("hello", store=store(), runner=make_runner(greeting_script()))
    assert result["conversation_id"]


@pytest.mark.asyncio
async def test_the_async_path_matches_the_sync_path() -> None:
    active = store()
    result = await run_chat_turn_async("hello", store=active, runner=make_runner(greeting_script()))

    assert result["state"].turn == 1
    assert result["state"].phase is Phase.IDLE
    assert active.get(result["conversation_id"]).turn == 1


# --- the per-turn runner --------------------------------------------------------------------


def test_each_turn_gets_its_own_session_service() -> None:
    """Shared ADK session state would race and would never be reclaimed."""
    agent = build_coordinator_agent(MockLlm([]))
    first = build_turn_runner(agent=agent)
    second = build_turn_runner(agent=agent)

    assert first is not second
    assert first.session_service is not second.session_service


def test_the_shared_agent_is_reused_across_turn_runners() -> None:
    """The agent tree is the expensive part, so it is the part that is shared."""
    agent = build_coordinator_agent(MockLlm([]))
    assert build_turn_runner(agent=agent).agent is build_turn_runner(agent=agent).agent
