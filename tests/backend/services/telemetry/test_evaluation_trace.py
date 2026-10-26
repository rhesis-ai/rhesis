"""The trace a metric reads: stored spans first, the run's unsaved spans until they are, and
one built from the response when there are neither."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from rhesis.telemetry.schemas import OTELSpan

from rhesis.backend.app.services.invokers.reported_spans import reported_spans
from rhesis.backend.app.services.telemetry import evaluation_trace
from rhesis.backend.app.services.telemetry.evaluation_trace import (
    evaluation_trace_loader,
    load_evaluation_trace,
    trace_from_response,
    with_live_values,
)
from rhesis.backend.metrics.inputs import EvaluationInputs

TRACE_ID = "a" * 32
ORG = "11111111-1111-1111-1111-111111111111"
PROJECT = "22222222-2222-2222-2222-222222222222"
START = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def _row(span_id, parent, name, offset, span_type="span", attributes=None):
    return SimpleNamespace(
        id=f"row-{span_id}",
        span_id=span_id,
        parent_span_id=parent,
        span_name=name,
        span_kind="INTERNAL",
        span_type=span_type,
        start_time=START + timedelta(seconds=offset),
        end_time=START + timedelta(seconds=offset + 1),
        status_code="OK",
        status_message=None,
        attributes=attributes or {},
        events=[],
    )


@contextmanager
def _session():
    yield object()


def _stored(rows):
    return (
        patch.object(evaluation_trace, "get_db_with_tenant_variables", lambda *a: _session()),
        patch.object(evaluation_trace, "get_trace_by_id", lambda *a, **k: rows),
    )


def test_stored_spans_become_the_tree_the_api_returns():
    rows = [
        _row("r" * 16, None, "function.endpoint_sdk_invoke", 0),
        _row("t" * 16, "r" * 16, "ai.tool.invoke", 2, "tool.invoke", {"ai.tool.name": "book"}),
        _row("l" * 16, "r" * 16, "ai.llm.invoke", 1, "llm.invoke"),
    ]
    db_patch, crud_patch = _stored(rows)
    with db_patch, crud_patch:
        trace = load_evaluation_trace(TRACE_ID, ORG, PROJECT)

    assert [s.span_name for s in trace.spans()] == [
        "function.endpoint_sdk_invoke",
        "ai.llm.invoke",
        "ai.tool.invoke",
    ]
    assert [s.tool_name for s in trace.spans(kind="tool.invoke")] == ["book"]
    assert trace.spans()[0].id == "row-" + "r" * 16


def test_before_a_batch_run_writes_its_spans_the_unsaved_ones_stand_in():
    invocation = OTELSpan(
        trace_id=TRACE_ID,
        span_id="b" * 16,
        project_id=PROJECT,
        span_name="function.endpoint_rest_invoke",
        start_time=START,
        end_time=START + timedelta(seconds=1),
        attributes={"rhesis.conversation.input": "Book a room"},
    )
    unsaved = [invocation, *reported_spans({"tool_calls": [{"name": "book"}]}, invocation)]

    db_patch, crud_patch = _stored([])
    with db_patch, crud_patch:
        trace = load_evaluation_trace(TRACE_ID, ORG, PROJECT, unsaved_spans=unsaved)

    [root] = trace.root_spans
    assert root.input == "Book a room"
    assert [child.tool_name for child in root.children] == ["book"]


def test_a_service_that_stored_first_still_nests_under_the_unsaved_invocation():
    """With traceparent, a service's spans can be stored before the invocation above them."""
    invocation = OTELSpan(
        trace_id=TRACE_ID,
        span_id="b" * 16,
        project_id=PROJECT,
        span_name="function.endpoint_rest_invoke",
        start_time=START,
        end_time=START + timedelta(seconds=3),
    )
    service_root = _row("c" * 16, "b" * 16, "ai.agent.invoke", 1, "agent.invoke")

    db_patch, crud_patch = _stored([service_root])
    with db_patch, crud_patch:
        trace = load_evaluation_trace(
            TRACE_ID, ORG, PROJECT, unsaved_spans=[invocation, _as_otel(service_root)]
        )

    [root] = trace.root_spans
    assert root.span_name == "function.endpoint_rest_invoke"
    assert [child.id for child in root.children] == ["row-" + "c" * 16]


def _as_otel(row):
    """The unsaved copy of a span that has since been stored."""
    return OTELSpan(
        trace_id=TRACE_ID,
        span_id=row.span_id,
        parent_span_id=row.parent_span_id,
        project_id=PROJECT,
        span_name=row.span_name,
        start_time=row.start_time,
        end_time=row.end_time,
    )


def test_reported_calls_fill_in_only_kinds_the_trace_lacks():
    rows = [
        _row("e" * 16, None, "function.endpoint_sdk_invoke", 0),
        _row("f" * 16, "e" * 16, "ai.tool.invoke", 1, "tool.invoke", {"ai.tool.name": "book"}),
    ]
    db_patch, crud_patch = _stored(rows)
    with db_patch, crud_patch:
        trace = with_live_values(
            load_evaluation_trace(TRACE_ID, ORG, PROJECT),
            "Book",
            "Booked.",
            context=["Rooms from 90 EUR."],
            tool_calls=[{"name": "book"}],
        )

    assert [c["name"] for c in trace.tool_calls] == ["book"]
    assert trace.context == ["Rooms from 90 EUR."]


def test_a_trace_built_from_the_response_says_so():
    root = trace_from_response("Hi", "Hello").root_spans[0]

    assert root.attributes["rhesis.trace.source"] == "response"


def test_a_trace_read_from_another_project_is_looked_up_there():
    other = "33333333-3333-3333-3333-333333333333"
    seen = {}

    def fake_load(trace_id, organization_id, project_id, *args):
        seen["project"] = project_id

    with patch.object(evaluation_trace, "load_evaluation_trace", fake_load):
        evaluation_trace_loader({"trace_id": TRACE_ID, "trace_project_id": other}, ORG, PROJECT)()

    assert seen["project"] == other


def test_nothing_stored_and_nothing_unsaved_is_none():
    db_patch, crud_patch = _stored([])
    with db_patch, crud_patch:
        assert load_evaluation_trace(TRACE_ID, ORG, PROJECT) is None


def test_a_result_without_a_trace_id_has_no_loader():
    assert evaluation_trace_loader({"output": "Hi"}, ORG, PROJECT) is None
    assert evaluation_trace_loader({"trace_id": TRACE_ID}, ORG, None) is None


def test_with_nothing_stored_the_trace_is_built_from_the_response():
    trace = trace_from_response(
        "Refund order 7",
        "Refunded.",
        context=["Refunds within 30 days."],
        tool_calls=[{"name": "issue_refund", "arguments": {"order": 7}}],
        metadata={"model": "small"},
    )

    assert (trace.input, trace.output) == ("Refund order 7", "Refunded.")
    assert trace.context == ["Refunds within 30 days."]
    assert trace.tool_calls == [{"name": "issue_refund", "arguments": {"order": 7}, "output": None}]
    assert trace.metadata == {"model": "small"}


def test_a_bare_response_still_has_its_invocation_span():
    trace = trace_from_response("Hi", "Hello")

    assert [s.span_name for s in trace.spans()] == ["function.endpoint_invoke"]
    assert (trace.context, trace.tool_calls, trace.metadata) == ([], [], {})


def test_the_live_answer_replaces_the_stored_copy_which_is_cut_short():
    rows = [
        _row(
            "r" * 16,
            None,
            "function.endpoint_rest_invoke",
            0,
            attributes={"rhesis.conversation.output": "Long answ"},
        )
    ]
    db_patch, crud_patch = _stored(rows)
    with db_patch, crud_patch:
        inputs = EvaluationInputs(
            input_text="Explain",
            output_text="Long answer, in full.",
            expected_output="",
            context=[],
            trace_loader=evaluation_trace_loader({"trace_id": TRACE_ID}, ORG, PROJECT),
        )
        trace = inputs.load_trace()

    assert trace.trace_id == TRACE_ID
    assert trace.output == "Long answer, in full."


def test_a_trace_that_cannot_be_read_falls_back_to_the_response():
    def unreadable():
        raise RuntimeError("database gone")

    inputs = EvaluationInputs(
        input_text="Hi",
        output_text="Hello",
        expected_output="",
        context=["Doc"],
        trace_loader=unreadable,
    )

    assert (inputs.load_trace().output, inputs.load_trace().context) == ("Hello", ["Doc"])
