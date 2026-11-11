"""The exchange an annotation judged: which turn a multi-turn annotation shows, and where a
trace's reply comes from when the span carries no conversation output."""

import json
from types import SimpleNamespace

from rhesis.backend.app.services.annotation_exchange import (
    _span_io,
    annotated_turn,
    conversation_turn,
)

SUMMARY = {
    "conversation_summary": [
        {"turn": 1, "penelope_message": "Hi", "target_response": "Where to?"},
        {"turn": 2, "penelope_message": "Rome", "target_response": "How many days?"},
    ]
}


def _annotation(target_type, reference=None):
    return SimpleNamespace(target_type=target_type, target_reference=reference)


class TestAnnotatedTurn:
    def test_turn_target_names_its_turn(self):
        assert annotated_turn(_annotation("turn", "Turn 2"), None) == 2

    def test_metric_target_takes_the_earliest_flagged_turn(self):
        metrics = {"metrics": {"Fidelity": {"relevant_turns": [4, 2, 3]}}}
        assert annotated_turn(_annotation("metric", "fidelity"), metrics) == 2

    def test_metric_without_flagged_turns_means_the_whole_conversation(self):
        metrics = {"metrics": {"Fidelity": {"relevant_turns": []}}}
        assert annotated_turn(_annotation("metric", "Fidelity"), metrics) is None
        assert annotated_turn(_annotation("metric", "Unknown"), metrics) is None
        assert annotated_turn(_annotation("metric", "Fidelity"), None) is None

    def test_whole_result_target_means_the_whole_conversation(self):
        assert annotated_turn(_annotation("test_result"), None) is None


class TestConversationTurn:
    def test_named_turn(self):
        assert conversation_turn(SUMMARY, 2) == ("Rome", "How many days?")

    def test_unnamed_or_missing_turn_falls_back_to_turn_one(self):
        assert conversation_turn(SUMMARY, None) == ("Hi", "Where to?")
        assert conversation_turn(SUMMARY, 9) == ("Hi", "Where to?")

    def test_single_turn_output_has_no_conversation(self):
        assert conversation_turn({"output": "Sure"}, None) is None
        assert conversation_turn(None, 1) is None


class TestSpanIo:
    def _span(self, **attributes):
        return SimpleNamespace(attributes=attributes)

    def test_conversation_attributes_win(self):
        span = self._span(
            **{
                "rhesis.conversation.input": "Hi",
                "rhesis.conversation.output": "Hello",
                "function.result": json.dumps({"response": "ignored"}),
            }
        )
        assert _span_io(span) == ("Hi", "Hello")

    def test_reply_falls_back_to_the_endpoint_result(self):
        span = self._span(
            **{
                "rhesis.conversation.input": "Hi",
                "function.result": json.dumps({"response": "Where to?", "phase": "greeting"}),
            }
        )
        assert _span_io(span) == ("Hi", "Where to?")

    def test_plain_text_result_is_used_as_is(self):
        span = self._span(**{"function.result": "Where to?"})
        assert _span_io(span) == (None, "Where to?")
