"""A multi-turn test is judged on the spans its conversation left, and on a trace built from the
conversation summary only when there are none."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from rhesis.backend.app.services.telemetry import evaluation_trace
from rhesis.backend.jobs.execution.evaluation import conversation_trace
from rhesis.sdk.entities.trace import Span, Trace

TRACE_ID = "c" * 32
ORG = "11111111-1111-1111-1111-111111111111"
PROJECT = "22222222-2222-2222-2222-222222222222"
START = datetime(2026, 11, 27, 9, 0, tzinfo=timezone.utc)

SUMMARY = [
    {"penelope_message": "Hi", "target_response": "Hello, how can I help?"},
    {"penelope_message": "Book a room", "target_response": "Booked for two."},
]


def _stored_conversation() -> Trace:
    def turn(index: int, said: str, answered: str) -> Span:
        start = START + timedelta(seconds=10 * index)
        return Span(
            span_id=f"{index}" * 16,
            span_name="function.endpoint_rest_invoke",
            start_time=start,
            end_time=start + timedelta(seconds=2),
            duration_ms=2000.0,
            status_code="OK",
            attributes={
                "rhesis.conversation.input": said,
                "rhesis.conversation.output": answered,
            },
        )

    return Trace(
        trace_id=TRACE_ID,
        project_id=PROJECT,
        root_spans=[turn(0, "Hi", "Hello, how"), turn(1, "Book a room", "Booked")],
    )


@pytest.mark.unit
class TestConversationTrace:
    def test_the_stored_spans_are_read_with_each_turn_in_full(self):
        seen = {}

        def load(trace_id, organization_id, project_id, *args):
            seen["trace_id"] = trace_id
            return _stored_conversation()

        with patch.object(evaluation_trace, "load_evaluation_trace", load):
            trace = conversation_trace(
                {"conversation_summary": SUMMARY, "trace_id": TRACE_ID}, ORG, PROJECT
            )

        assert seen["trace_id"] == TRACE_ID
        assert trace.trace_id == TRACE_ID
        assert [m.content for m in trace.messages().messages] == [
            "Hi",
            "Hello, how can I help?",
            "Book a room",
            "Booked for two.",
        ]
        assert [root.duration_ms for root in trace.root_spans] == [2000.0, 2000.0]

    def test_without_spans_the_trace_is_built_from_the_summary_with_no_timing(self):
        trace = conversation_trace({"conversation_summary": SUMMARY}, ORG, PROJECT)

        assert trace.is_conversation
        assert [m.content for m in trace.messages().messages][-1] == "Booked for two."
        assert {span.duration_ms for span in trace.spans()} == {None}

    def test_a_trace_that_cannot_be_read_falls_back_to_the_summary(self):
        def unreadable(*args):
            raise RuntimeError("database gone")

        with patch.object(evaluation_trace, "load_evaluation_trace", unreadable):
            trace = conversation_trace(
                {"conversation_summary": SUMMARY, "trace_id": TRACE_ID}, ORG, PROJECT
            )

        assert trace.trace_id != TRACE_ID
        assert len(trace.messages().messages) == 4

    def test_no_turns_is_nothing_to_judge(self):
        assert conversation_trace({"conversation_summary": []}) is None
