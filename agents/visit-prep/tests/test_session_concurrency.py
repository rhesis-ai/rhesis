"""Concurrency behaviour of the shared coordinator pipeline."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
from haystack.dataclasses import ChatMessage

from tests.mocks import MockChatGenerator, greeting_script
from visit_prep.pipeline import build_coordinator_pipeline
from visit_prep.session import StateStore, run_chat_turn, run_chat_turn_async

TURN_DELAY = 0.05


class SlowMockChatGenerator(MockChatGenerator):
    """Adds latency so overlapping turns actually overlap, and counts concurrency."""

    def __init__(self, responses: list[ChatMessage | str], *, delay: float = TURN_DELAY) -> None:
        super().__init__(responses)
        self._active_lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.delay = delay

    def run(self, messages, tools=None, **kwargs):
        with self._active_lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay)
            return super().run(messages, tools=tools, **kwargs)
        finally:
            with self._active_lock:
                self.active -= 1


def _greeting_pipeline(turns: int = 20):
    responses: list[ChatMessage] = []
    for _ in range(turns):
        responses.extend(greeting_script())
    generator = SlowMockChatGenerator(responses)
    return build_coordinator_pipeline(generator=generator), generator


def test_sync_turns_on_one_conversation_do_not_lose_updates():
    """Overlapping turns on one id must serialize their read-modify-write."""
    pipeline, _ = _greeting_pipeline()
    store = StateStore()
    conv_id = "shared-conversation"
    turns = 5
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            run_chat_turn("hello", conversation_id=conv_id, store=store, pipeline=pipeline)
        except BaseException as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(turns)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert store.get(conv_id).turn == turns


@pytest.mark.asyncio
async def test_async_turns_across_conversations_run_concurrently():
    """Regression guard: a lock held across the await used to wedge the whole event loop.

    A blocking lock acquired on the event loop thread while the holder is a suspended
    coroutine can never be released, so this used to hang forever rather than fail.
    """
    pipeline, generator = _greeting_pipeline()
    store = StateStore()
    turns = 5

    started = time.perf_counter()
    results = await asyncio.wait_for(
        asyncio.gather(
            *[
                run_chat_turn_async(
                    "hello", conversation_id=f"conv-{i}", store=store, pipeline=pipeline
                )
                for i in range(turns)
            ]
        ),
        timeout=20,
    )
    elapsed = time.perf_counter() - started

    assert len(results) == turns
    assert all(r["state"].turn == 1 for r in results)
    assert generator.max_active > 1, "turns on different conversations must overlap"
    # Serialized, this would take at least turns * 2 * TURN_DELAY.
    assert elapsed < turns * 2 * TURN_DELAY


@pytest.mark.asyncio
async def test_async_turns_on_one_conversation_serialize():
    """One conversation still serializes, so no turn reads stale state."""
    pipeline, _ = _greeting_pipeline()
    store = StateStore()
    conv_id = "one-conversation"
    turns = 5

    await asyncio.wait_for(
        asyncio.gather(
            *[
                run_chat_turn_async(
                    "hello", conversation_id=conv_id, store=store, pipeline=pipeline
                )
                for _ in range(turns)
            ]
        ),
        timeout=20,
    )
    assert store.get(conv_id).turn == turns
