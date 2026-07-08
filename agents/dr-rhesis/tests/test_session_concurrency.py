"""Concurrency guards for the shared default pipeline."""

from __future__ import annotations

import threading
import time

import pytest

from dr_rhesis import session as session_mod
from dr_rhesis.pipeline import build_intent_pipeline, build_turn_components
from dr_rhesis.session import StateStore, run_chat_turn
from tests.mocks import MockChatGenerator


class SlowMockChatGenerator(MockChatGenerator):
    """Tracks how many generator calls overlap in time."""

    def __init__(self, responses: list[str], *, delay: float = 0.05) -> None:
        super().__init__(responses)
        self._active_lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.delay = delay

    def run(self, messages, **kwargs):
        with self._active_lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay)
            return super().run(messages, **kwargs)
        finally:
            with self._active_lock:
                self.active -= 1


@pytest.fixture
def shared_mock_pipeline(monkeypatch):
    """Install a slow mock-backed default pipeline for concurrency tests."""
    generator = SlowMockChatGenerator(['{"intent": "greeting"}'] * 20)
    components = build_turn_components(generator=generator)
    pipeline = build_intent_pipeline(components)
    monkeypatch.setattr(session_mod, "_default_pipeline", pipeline)
    return generator


def test_shared_pipeline_serializes_concurrent_turns(shared_mock_pipeline):
    """Concurrent /chat turns must not overlap on the cached pipeline."""
    store = StateStore()
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            run_chat_turn(f"hello {index}", conversation_id=f"conv-{index}", store=store)
        except BaseException as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert shared_mock_pipeline.max_active == 1
