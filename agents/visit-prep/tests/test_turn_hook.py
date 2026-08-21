"""The ``turn_hook`` seam in the untraced loops must work with a real turn object.

Regression guard: the loops called ``turn.set_output(...)`` while the hook yields an object
exposing ``output`` as a property, so every traced run died on the first reply. Nothing caught
it because the other tests drive these loops with ``turn_hook=None``.
"""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests import integrations
from tests.mocks import greeting_script, make_pipeline

CHAT_DIR = Path(__file__).resolve().parent.parent / "chat_terminal"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
for _directory in (CHAT_DIR, EXAMPLES_DIR):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))


class RecordingTurn:
    """Stands in for ConversationTurn, exposing the same ``output`` property."""

    def __init__(self, user_input: str) -> None:
        self.user_input = user_input
        self._output = ""

    @property
    def output(self) -> str:
        return self._output

    @output.setter
    def output(self, reply: str) -> None:
        self._output = reply


@pytest.fixture
def turn_hook():
    """A hook with the same shape as ``RhesisTracing.turn``, recording what it is given."""
    turns: list[RecordingTurn] = []

    @contextmanager
    def hook(user_input: str):
        turn = RecordingTurn(user_input)
        turns.append(turn)
        yield turn

    hook.turns = turns
    return hook


def test_conversation_turn_matches_the_real_handle(integration):
    """The stand-in must not drift from either integration's ConversationTurn."""
    module = importlib.import_module(
        integrations.NATIVE_MODULE if integration.name == "native" else integrations.UPSTREAM_MODULE
    )

    real = module.ConversationTurn()
    real.output = "reply"
    assert real.output == "reply"
    # The loops assign `output`; there is deliberately no setter method to drift from.
    assert not hasattr(real, "set_output")


def test_run_scenario_feeds_the_turn_hook(turn_hook):
    from run_scenarios import run_scenario

    run_scenario(
        "greeting",
        ["Hello!"],
        pipeline=make_pipeline(greeting_script()),
        turn_hook=turn_hook,
    )

    (turn,) = turn_hook.turns
    assert turn.user_input == "Hello!"
    assert "visit-preparation assistant" in turn.output


def test_chat_main_feeds_the_turn_hook(turn_hook, monkeypatch):
    import chat as chat_module

    from visit_prep import session as session_mod

    monkeypatch.setattr(session_mod, "_default_pipeline", make_pipeline(greeting_script()))
    replies = iter(["Hello!", "quit"])
    monkeypatch.setattr("builtins.input", lambda *_: next(replies))

    assert chat_module.main(turn_hook=turn_hook) == 0

    (turn,) = turn_hook.turns
    assert turn.user_input == "Hello!"
    assert "visit-preparation assistant" in turn.output
