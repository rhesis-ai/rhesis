"""Session-layer regression tests."""

from __future__ import annotations

import pytest

from tests.mocks import greeting_script, make_pipeline
from visit_prep.session import StateStore, run_chat_turn, run_chat_turn_async


def test_run_chat_turn_carries_state_across_turns():
    pipeline = make_pipeline([*greeting_script(), *greeting_script()])
    store = StateStore()

    first = run_chat_turn("hello", store=store, pipeline=pipeline)
    second = run_chat_turn(
        "hi again",
        conversation_id=first["conversation_id"],
        store=store,
        pipeline=pipeline,
    )

    assert second["conversation_id"] == first["conversation_id"]
    assert second["state"].turn == 2
    assert store.get(first["conversation_id"]).turn == 2


def test_delete_forgets_conversation_and_its_locks():
    store = StateStore()
    result = run_chat_turn("hello", store=store, pipeline=make_pipeline(greeting_script()))
    conv_id = result["conversation_id"]

    assert store.delete(conv_id) is True
    assert store.delete(conv_id) is False
    assert conv_id not in store.list_conversations()


@pytest.mark.asyncio
async def test_async_turn_matches_the_sync_turn():
    store = StateStore()
    result = await run_chat_turn_async(
        "hello", store=store, pipeline=make_pipeline(greeting_script())
    )
    assert result["state"].turn == 1
    assert "visit-preparation assistant" in result["response"]
    assert store.get(result["conversation_id"]).turn == 1
