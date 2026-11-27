"""What a response reports becomes part of the invocation's trace."""

from datetime import datetime, timedelta, timezone

import pytest
from rhesis.telemetry.schemas import OTELSpan

from rhesis.sdk.entities.trace import Span
from rhesis.sdk.telemetry.reported_spans import (
    MAX_REPORTED_VALUE_LENGTH,
    reported_attributes,
    reported_spans,
)

START = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def _invocation():
    return OTELSpan(
        trace_id="a" * 32,
        span_id="b" * 16,
        project_id="p",
        span_name="function.endpoint_rest_invoke",
        start_time=START,
        end_time=START + timedelta(seconds=2),
    )


def _as_sdk(span: OTELSpan) -> Span:
    """Read a reported span the way a metric will."""
    return Span(
        span_id=span.span_id,
        span_name=span.span_name,
        attributes=span.attributes,
        events=[event.model_dump() for event in span.events],
    )


def test_each_flat_tool_call_is_a_tool_span():
    result = {
        "output": "Booked.",
        "tool_calls": [
            {"name": "find_room", "arguments": {"city": "Paris"}, "output": "Room 4"},
            {"name": "book", "arguments": '{"room": 4}'},
        ],
    }

    spans = [_as_sdk(s) for s in reported_spans(result, _invocation())]

    assert [(s.kind, s.tool_name) for s in spans] == [
        ("tool.invoke", "find_room"),
        ("tool.invoke", "book"),
    ]
    assert (spans[0].input, spans[0].output) == ('{"city": "Paris"}', "Room 4")
    assert (spans[1].input, spans[1].output) == ('{"room": 4}', None)


def test_openai_shaped_tool_calls_are_read_too():
    result = {
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}
        ]
    }

    [span] = [_as_sdk(s) for s in reported_spans(result, _invocation())]

    assert (span.tool_name, span.input) == ("lookup", "{}")


def test_a_null_field_does_not_hide_the_value_beside_it():
    """Some mappers emit ``"arguments": null`` next to OpenAI's ``function.arguments``."""
    result = {
        "tool_calls": [
            {
                "arguments": None,
                "output": None,
                "result": "booked",
                "function": {"name": "book", "arguments": '{"room": 4}'},
            }
        ]
    }

    [span] = [_as_sdk(s) for s in reported_spans(result, _invocation())]

    assert (span.input, span.output) == ('{"room": 4}', "booked")


def test_context_is_one_retrieval_span():
    result = {"context": ["Refunds take 5 days.", "Contact support."]}

    [span] = [_as_sdk(s) for s in reported_spans(result, _invocation())]

    assert span.kind == "retrieval"
    assert span.output == '["Refunds take 5 days.", "Contact support."]'


def test_they_hang_off_the_invocation_and_say_they_were_reported():
    parent = _invocation()

    spans = reported_spans({"tool_calls": [{"name": "t"}], "context": "doc"}, parent)

    assert {s.parent_span_id for s in spans} == {parent.span_id}
    assert {s.trace_id for s in spans} == {parent.trace_id}
    assert {s.attributes["rhesis.span.source"] for s in spans} == {"reported"}
    assert len({s.span_id for s in spans}) == len(spans)


def test_they_start_in_the_order_reported_so_storage_keeps_it():
    """Stored spans come back ordered by start time; equal times would shuffle them."""
    parent = _invocation()

    spans = reported_spans({"tool_calls": [{"name": "a"}, {"name": "b"}], "context": "doc"}, parent)

    starts = [s.start_time for s in spans]
    assert starts == sorted(starts) and len(set(starts)) == len(starts)
    assert all(parent.start_time <= s.start_time <= s.end_time for s in spans)


def test_a_response_that_reports_nothing_adds_nothing():
    assert reported_spans({"output": "Hi"}, _invocation()) == []
    assert reported_spans(None, _invocation()) == []


def test_they_claim_no_timing_of_their_own():
    """The endpoint said what happened, not how long it took."""
    spans = reported_spans(
        {"tool_calls": [{"name": "a", "output": "x"}], "context": "doc"}, _invocation()
    )

    assert all(s.start_time == s.end_time for s in spans)
    assert all(e.timestamp == s.start_time for s in spans for e in s.events)


@pytest.mark.parametrize(
    "usage, expected",
    [
        (
            {"prompt_tokens": 12, "completion_tokens": 30, "total_tokens": 42},
            {"ai.llm.tokens.input": 12, "ai.llm.tokens.output": 30, "ai.llm.tokens.total": 42},
        ),
        (
            {"input_tokens": 5, "output_tokens": 7},
            {"ai.llm.tokens.input": 5, "ai.llm.tokens.output": 7},
        ),
        ('{"input_tokens": 5}', {"ai.llm.tokens.input": 5}),
    ],
    ids=["openai", "anthropic", "json text"],
)
def test_usage_is_one_model_call_with_its_token_counts(usage, expected):
    [span] = reported_spans({"usage": usage}, _invocation())

    assert span.attributes["ai.operation.type"] == "llm.invoke"
    assert {k: v for k, v in span.attributes.items() if k.startswith("ai.llm.tokens")} == expected


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": "many"}, "not json", 12])
def test_usage_without_token_counts_adds_no_span(usage):
    assert reported_spans({"usage": usage}, _invocation()) == []


class TestReportedAttributes:
    def test_each_metadata_key_is_one_attribute(self):
        attrs = reported_attributes(
            {"metadata": {"confidence": 0.7, "tags": ["a"], "note": None, "ok": True}}
        )

        assert attrs == {
            "rhesis.reported.metadata.confidence": 0.7,
            "rhesis.reported.metadata.tags": '["a"]',
            "rhesis.reported.metadata.ok": True,
        }

    def test_a_long_value_is_cut_on_its_own(self):
        attrs = reported_attributes({"metadata": {"blob": "x" * 5000, "short": "y"}})

        assert len(attrs["rhesis.reported.metadata.blob"]) == MAX_REPORTED_VALUE_LENGTH
        assert attrs["rhesis.reported.metadata.short"] == "y"

    def test_metadata_given_as_json_text_is_read(self):
        attrs = reported_attributes({"metadata": '{"channel": "email"}'})
        assert attrs == {"rhesis.reported.metadata.channel": "email"}

    def test_other_fields_are_kept_when_the_response_set_them(self):
        attrs = reported_attributes({"intent": "refund", "missing": None}, ["intent", "missing"])
        assert attrs == {"rhesis.reported.intent": "refund"}

    def test_nothing_reported_gives_no_attributes(self):
        assert reported_attributes(None) == {}
        assert reported_attributes({"output": "Hi"}) == {}
