"""Per-conversation serialization and cross-conversation concurrency.

The async tests carry a timeout because the failure they guard against is a hang, not a wrong
answer: a ``threading.Lock`` held across an ``await`` blocks the event loop thread and the
coroutine holding it can never resume. Without the timeout the suite would stall rather than
fail.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from google.adk.models import LlmRequest, LlmResponse
from pydantic import PrivateAttr

from reg_advisor import session as session_mod
from reg_advisor.runner import build_coordinator_agent
from reg_advisor.session import StateStore, run_chat_turn, run_chat_turn_async
from tests.mocks import MockLlm, greeting_script

TURN_DELAY = 0.05
TIMEOUT = 20


class SlowMockLlm(MockLlm):
    """A mock that takes measurable time and records how many calls overlap."""

    _delay: float = PrivateAttr(default=TURN_DELAY)
    _counter_lock: Lock = PrivateAttr(default_factory=Lock)
    _active: int = PrivateAttr(default=0)
    _max_active: int = PrivateAttr(default=0)

    def __init__(self, responses: list[LlmResponse], delay: float = TURN_DELAY) -> None:
        super().__init__(responses)
        self._delay = delay

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        with self._counter_lock:
            self._active += 1
            self._max_active = max(self._max_active, self._active)
        try:
            await asyncio.sleep(self._delay)
            async for response in super().generate_content_async(llm_request, stream):
                yield response
        finally:
            with self._counter_lock:
                self._active -= 1

    @property
    def max_active(self) -> int:
        return self._max_active


def install_agent(monkeypatch: pytest.MonkeyPatch, model: MockLlm) -> None:
    """Point the process-wide agent at a scripted model.

    Each turn still builds its own ``Runner`` and session service, so this exercises the real
    production path rather than a shared-runner shortcut.
    """
    monkeypatch.setattr(session_mod, "_default_agent", build_coordinator_agent(model))


def greeting_turns(count: int, *, delay: float = TURN_DELAY) -> SlowMockLlm:
    """A model scripted for ``count`` identical greeting turns.

    Every reply in the script is interchangeable, so the order threads consume them in does not
    matter — which is what makes a shared queue usable across concurrent turns.
    """
    return SlowMockLlm([r for _ in range(count) for r in greeting_script()], delay=delay)


# --- one conversation must serialize -----------------------------------------------------------


def test_concurrent_threads_on_one_conversation_do_not_lose_updates() -> None:
    turns = 5
    store = StateStore()
    conv_id = "shared"

    with pytest.MonkeyPatch.context() as monkeypatch:
        install_agent(monkeypatch, greeting_turns(turns))
        with ThreadPoolExecutor(max_workers=turns) as pool:
            list(
                pool.map(
                    lambda _: run_chat_turn("hello", conversation_id=conv_id, store=store),
                    range(turns),
                )
            )

    assert store.get(conv_id).turn == turns, "every turn was recorded"
    assert len(store.get(conv_id).history) == turns * 2


@pytest.mark.asyncio
async def test_async_turns_on_one_conversation_still_serialize() -> None:
    turns = 4
    store = StateStore()
    conv_id = "shared"
    model = greeting_turns(turns)

    with pytest.MonkeyPatch.context() as monkeypatch:
        install_agent(monkeypatch, model)
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    run_chat_turn_async("hello", conversation_id=conv_id, store=store)
                    for _ in range(turns)
                ]
            ),
            timeout=TIMEOUT,
        )

    assert model.max_active == 1, "turns on one conversation never overlapped"
    assert store.get(conv_id).turn == turns


# --- different conversations must overlap --------------------------------------------------------


@pytest.mark.asyncio
async def test_async_turns_across_conversations_run_concurrently() -> None:
    conversations = 5
    store = StateStore()
    model = greeting_turns(conversations)

    with pytest.MonkeyPatch.context() as monkeypatch:
        install_agent(monkeypatch, model)
        started = time.monotonic()
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    run_chat_turn_async("hello", conversation_id=f"c{n}", store=store)
                    for n in range(conversations)
                ]
            ),
            timeout=TIMEOUT,
        )
        elapsed = time.monotonic() - started

    assert model.max_active > 1, "turns on different conversations overlapped"
    assert elapsed < conversations * 2 * TURN_DELAY, "they did not run one after another"
    assert store.list_conversations() == {f"c{n}": 1 for n in range(conversations)}


@pytest.mark.asyncio
async def test_the_async_path_never_blocks_the_event_loop() -> None:
    """A threading.Lock held across an await would stop this heartbeat dead."""
    store = StateStore()
    ticks = 0

    async def heartbeat() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    with pytest.MonkeyPatch.context() as monkeypatch:
        install_agent(monkeypatch, greeting_turns(2, delay=0.1))
        beat = asyncio.create_task(heartbeat())
        await asyncio.wait_for(
            asyncio.gather(
                run_chat_turn_async("hello", conversation_id="a", store=store),
                run_chat_turn_async("hello", conversation_id="b", store=store),
            ),
            timeout=TIMEOUT,
        )
        beat.cancel()

    assert ticks > 3, "the loop kept running while turns were in flight"


def test_threads_on_different_conversations_do_not_interfere() -> None:
    conversations = 4
    store = StateStore()

    with pytest.MonkeyPatch.context() as monkeypatch:
        install_agent(monkeypatch, greeting_turns(conversations))
        with ThreadPoolExecutor(max_workers=conversations) as pool:
            list(
                pool.map(
                    lambda n: run_chat_turn("hello", conversation_id=f"c{n}", store=store),
                    range(conversations),
                )
            )

    assert store.list_conversations() == {f"c{n}": 1 for n in range(conversations)}
