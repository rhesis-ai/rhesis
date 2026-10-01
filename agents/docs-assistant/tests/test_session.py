import asyncio

from docs_assistant.session import ConversationStore
from docs_assistant.state import TurnRecord
from tests.conftest import FakeClock


async def add_turn(store, conversation_id, question="q"):
    async with store.turn(conversation_id) as state:
        state.turns.append(TurnRecord(question, "answered"))
        return state.conversation_id


async def test_a_conversation_keeps_its_turns():
    store = ConversationStore()
    cid = await add_turn(store, None)
    await add_turn(store, cid)
    assert store.list() == {cid: 2}


async def test_an_unknown_id_starts_fresh_under_that_id():
    store = ConversationStore()
    assert await add_turn(store, "abc") == "abc"
    assert store.list() == {"abc": 1}


async def test_idle_conversations_expire():
    clock = FakeClock()
    store = ConversationStore(idle_ttl=60, clock=clock)
    cid = await add_turn(store, None)
    clock.now += 61
    assert store.list() == {}
    async with store.turn(cid) as state:
        assert state.turns == []


async def test_the_oldest_conversation_is_evicted_at_the_cap():
    store = ConversationStore(max_conversations=2)
    await add_turn(store, "a")
    await add_turn(store, "b")
    await add_turn(store, "a")  # touching "a" makes "b" the oldest
    await add_turn(store, "c")
    assert set(store.list()) == {"a", "c"}


async def test_delete():
    store = ConversationStore()
    await add_turn(store, "a")
    assert store.delete("a") is True
    assert store.delete("a") is False


async def test_turns_on_one_conversation_run_one_at_a_time():
    store = ConversationStore()
    events = []

    async def slow_turn(name):
        async with store.turn("c1") as state:
            events.append(f"{name} start, saw {state.turn}")
            await asyncio.sleep(0.01)
            state.turns.append(TurnRecord(name, "answered"))
            events.append(f"{name} end")

    await asyncio.gather(slow_turn("one"), slow_turn("two"))
    assert events == ["one start, saw 0", "one end", "two start, saw 1", "two end"]
    assert store.list() == {"c1": 2}


async def test_different_conversations_run_side_by_side():
    store = ConversationStore()
    events = []

    async def slow_turn(cid):
        async with store.turn(cid):
            events.append(f"{cid} start")
            await asyncio.sleep(0.01)
            events.append(f"{cid} end")

    await asyncio.gather(slow_turn("a"), slow_turn("b"))
    assert events[:2] == ["a start", "b start"]
