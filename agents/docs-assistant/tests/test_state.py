import pytest

from docs_assistant.schemas import Clarification
from docs_assistant.state import ConversationState, PendingClarification, TurnRecord, match_option

OPTIONS = ["In the Rhesis web app", "In the Python SDK"]


@pytest.mark.parametrize(
    ("reply", "picked"),
    [
        ("2", "In the Python SDK"),
        ("option 1", "In the Rhesis web app"),
        ("1.", "In the Rhesis web app"),
        ("the SDK", "In the Python SDK"),
        ("python sdk", "In the Python SDK"),
        ("web app", "In the Rhesis web app"),
    ],
)
def test_replies_pick_an_option(reply, picked):
    assert match_option(reply, OPTIONS) == picked


@pytest.mark.parametrize(
    "reply", ["3", "both, the SDK and the web app", "how do I install it?", "", "rhesis"]
)
def test_unclear_replies_pick_nothing(reply):
    assert match_option(reply, OPTIONS) is None


def test_history_lists_recent_turns_and_the_pending_question():
    state = ConversationState("c1")
    for n in range(8):
        state.turns.append(TurnRecord(f"q{n}", "answered", [f"https://docs.rhesis.ai/p{n}"]))
    state.pending = PendingClarification(
        question="how do I add a metric?",
        clarification=Clarification(question="Where?", options=OPTIONS),
        language="en",
    )
    history = state.history()
    assert "q1" not in history and "q2" in history and "q7" in history
    assert "cited: https://docs.rhesis.ai/p7" in history
    assert "you asked back: Where? (options: In the Rhesis web app; In the Python SDK)" in history
    assert state.turn == 8
