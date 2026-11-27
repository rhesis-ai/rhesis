"""What a span target's conversation readers read, and the SDK clients for the attribute
catalogue and the target preview."""

from unittest.mock import patch

import pytest

from rhesis.sdk.clients import Endpoints, Methods
from rhesis.sdk.entities.project import Project
from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.metrics.targets import Target


def span(kind, name, children=(), **attributes):
    attrs = {key.replace("__", "."): value for key, value in attributes.items()}
    if kind == "tool.invoke":
        attrs.setdefault("ai.tool.name", name)
    if kind == "agent.invoke":
        attrs.setdefault("ai.agent.name", name)
    return Span(
        span_id=f"{kind}-{name}-{id(attrs)}",
        span_name=name,
        span_type=kind,
        attributes=attrs,
        children=list(children),
    )


def turn(asked, answered, order):
    refund = span("tool.invoke", "issue_refund", ai__tool__output=order)
    billing = span("agent.invoke", "billing_agent", children=[refund])
    triage = span("agent.invoke", "triage_agent", children=[billing])
    return span(
        "endpoint.invoke",
        "POST /v1/chat",
        children=[triage],
        rhesis__conversation__input=asked,
        rhesis__conversation__output=answered,
    )


def trace_of(*roots):
    trace = Trace(trace_id="t1", root_spans=list(roots))
    trace._detail_loaded = True
    return trace


# ---------------------------------------------------------------------------
# Conversation readers read the turn
# ---------------------------------------------------------------------------


def test_a_tool_call_deep_in_a_turn_reads_the_turn():
    target = Target.spans(
        kind="tool_call", read={"input": "conversation.input", "output": "conversation.output"}
    )

    [unit] = target.select(trace_of(turn("I was charged twice", "Refunded.", "ORD-1")))

    assert (unit.input, unit.output) == ("I was charged twice", "Refunded.")


def test_a_tool_call_in_the_second_turn_reads_that_turn():
    trace = trace_of(turn("Refund order 1", "Done.", "1"), turn("And order 2?", "Also done.", "2"))
    target = Target.spans(kind="tool_call", read=("conversation.input", None))

    units = target.select(trace)

    assert [(u.input, u.output) for u in units] == [("Refund order 1", "1"), ("And order 2?", "2")]


def test_a_conversation_reader_falls_back_to_the_span_itself():
    lone = span("tool.invoke", "lookup", rhesis__conversation__input="asked on the span")
    trace = trace_of(span("function", "root", children=[lone]))

    [unit] = Target.spans(kind="tool_call", read={"input": "conversation.input"}).select(trace)

    assert unit.input == "asked on the span"


# ---------------------------------------------------------------------------
# Clients for the catalogue and the preview
# ---------------------------------------------------------------------------


@patch("rhesis.sdk.entities.project.APIClient")
def test_trace_attributes_asks_for_the_project_s_catalogue(mock_client):
    catalogue = {"kinds": {"tool.invoke": {"spans": 3, "attributes": []}}, "sampled_spans": 3}
    mock_client.return_value.send_request.return_value = catalogue

    result = Project(id="p1").trace_attributes(kind="tool_call", days=3)

    assert result == catalogue
    mock_client.return_value.send_request.assert_called_once_with(
        endpoint=Endpoints.TELEMETRY_ATTRIBUTES,
        method=Methods.GET,
        params={"project_id": "p1", "days": 3, "kind": "tool.invoke"},
    )


@patch("rhesis.sdk.entities.project.APIClient")
def test_trace_attributes_without_a_kind_asks_for_every_kind(mock_client):
    Project(id="p1").trace_attributes()

    params = mock_client.return_value.send_request.call_args.kwargs["params"]
    assert params == {"project_id": "p1", "days": 7}


@patch("rhesis.sdk.clients.APIClient")
def test_preview_sends_the_stored_form_of_the_target(mock_client):
    answer = {"traces": 20, "matching_traces": 2, "units": 3, "samples": []}
    mock_client.return_value.send_request.return_value = answer
    target = Target.coerce({"on": "tool_call", "where": {"app.tier": "gold"}})

    assert target.preview(Project(id="p1"), traces=20) == answer
    mock_client.return_value.send_request.assert_called_once_with(
        endpoint=Endpoints.METRIC_TARGET_PREVIEW,
        method=Methods.POST,
        data={"project_id": "p1", "target": target.to_config(), "traces": 20},
    )


@patch("rhesis.sdk.clients.APIClient")
def test_preview_takes_a_project_id(mock_client):
    Target(on="turn").preview("p2")

    data = mock_client.return_value.send_request.call_args.kwargs["data"]
    assert data == {"project_id": "p2", "target": {"on": "turn"}, "traces": 50}


def test_preview_needs_a_project_with_an_id():
    with pytest.raises(ValueError, match="needs a project with an id"):
        Target(on="turn").preview(Project())
