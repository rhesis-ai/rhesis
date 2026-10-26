"""Tool calls and context a response reports become child spans of the invocation."""

from datetime import datetime, timedelta, timezone

from rhesis.telemetry.schemas import OTELSpan

from rhesis.sdk.telemetry.reported_spans import reported_spans
from rhesis.sdk.entities.trace import Span

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
