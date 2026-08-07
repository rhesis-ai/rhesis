"""Assert coordinator → specialist handoffs nest in the Haystack/Rhesis span tree."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from haystack import tracing
from haystack.tracing import disable_tracing
from haystack_integrations.tracing.rhesis import RhesisTracing
from haystack_integrations.tracing.rhesis.tracer import (
    RhesisTelemetry,
    RhesisTracer,
    rhesis_invocation_context,
)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.exporter import RhesisOTLPExporter
from rhesis.telemetry.schemas import AIOperationType

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.context import set_root_trace_id
from tests.mocks import gather_script, greeting_script, make_pipeline
from visit_prep.pipeline import run_turn
from visit_prep.state import VisitPrepState

TURN_SPAN_NAME = "function.visit_prep_turn"


@contextmanager
def _rhesis_tracing(provider: TracerProvider):
    telemetry = RhesisTelemetry(
        provider=provider,
        otel_tracer=provider.get_tracer("visit-prep-span-tree"),
        project_id="proj-test",
        environment="test",
        base_url="http://localhost:8080",
    )
    rhesis_tracer = RhesisTracer(telemetry=telemetry, name="visit-prep-test")
    rhesis_tracer.enforce_flush = False
    previous = tracing.tracer.is_content_tracing_enabled
    tracing.tracer.is_content_tracing_enabled = True
    tracing.enable_tracing(rhesis_tracer)
    try:
        yield
    finally:
        disable_tracing()
        tracing.tracer.is_content_tracing_enabled = previous


@pytest.fixture
def traced_stack():
    """Yield ``(exporter, provider)`` with Haystack traced onto that provider."""
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with _rhesis_tracing(provider):
        try:
            yield exporter, provider
        finally:
            exporter.clear()


@pytest.fixture
def traced_exporter(traced_stack):
    exporter, _ = traced_stack
    return exporter


@pytest.fixture
def script_tracing(traced_stack, monkeypatch):
    """Yield ``(exporter, tracing)`` set up as a traced script has it.

    The connector is stubbed and the global tracer redirected, so ``RhesisTracing`` runs
    against the in-memory exporter instead of a backend.
    """
    exporter, provider = traced_stack

    class _StubConnector:
        def __init__(self, name, **kwargs):
            self.tracer = provider

    import haystack_integrations.components.connectors.rhesis as connector_module

    monkeypatch.setenv("RHESIS_API_KEY", "test-key")
    monkeypatch.setattr(connector_module, "RhesisConnector", _StubConnector)
    monkeypatch.setattr(trace, "get_tracer", lambda *a, **k: provider.get_tracer("visit-prep-turn"))
    tracing_instance = RhesisTracing("Visit-Prep-Test", turn_span_name=TURN_SPAN_NAME)
    assert tracing_instance.enabled
    return exporter, tracing_instance


def _parent_of(span: Any, spans: list[Any]) -> Any | None:
    parent_id = span.parent.span_id if span.parent else None
    if parent_id is None:
        return None
    for candidate in spans:
        if candidate.context.span_id == parent_id:
            return candidate
    return None


def test_gather_history_handoff_nests_agent_spans(traced_exporter):
    exporter = traced_exporter
    msg = "I have a headache"
    result = run_turn(msg, VisitPrepState(), pipeline=make_pipeline(gather_script(msg)))
    assert "?" in result["response"]

    spans = list(exporter.get_finished_spans())
    names = {s.name for s in spans}
    assert "function.haystack.pipeline.run" in names
    assert AIOperationType.AGENT_INVOKE in names
    assert AIOperationType.LLM_INVOKE in names

    agent_spans = [s for s in spans if s.name == AIOperationType.AGENT_INVOKE]
    assert len(agent_spans) >= 2  # coordinator + history specialist

    handoffs = [s for s in spans if s.name == AIOperationType.AGENT_HANDOFF]
    tools = [s for s in spans if s.name == AIOperationType.TOOL_INVOKE]
    handoff_or_tool = handoffs or tools
    assert handoff_or_tool

    # At least one nested agent under a tool/handoff parent.
    nested = [s for s in agent_spans if _parent_of(s, spans) in handoff_or_tool]
    assert nested, "expected history specialist agent.invoke under gather_history handoff"

    if handoffs:
        assert any(
            h.attributes.get(AIAttributes.AGENT_HANDOFF_TO) == "gather_history" for h in handoffs
        )


def _sdk_endpoint_span(provider: TracerProvider):
    """Mimic the SDK ``@endpoint`` span for turn 2+ of a conversation.

    The SDK attaches a synthetic parent to pull the turn onto the conversation's trace id, then
    marks the span as the turn root so the exporter strips that placeholder again.
    """
    synthetic_parent = NonRecordingSpan(
        SpanContext(
            trace_id=int("cc" * 16, 16),
            span_id=ConversationContext.SYNTHETIC_PARENT_SPAN_ID,
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    )
    return provider.get_tracer("visit-prep-endpoint").start_as_current_span(
        "function.visit_prep_chat",
        context=trace.set_span_in_context(synthetic_parent),
    )


def test_pipeline_span_nests_under_sdk_endpoint_span(traced_stack):
    """One turn must yield one turn root, with the Haystack tree hanging off it.

    Regression guard: the pipeline span used to claim ``is_turn_root``, which made the exporter
    strip its real parent. The subtree detached and the UI showed a second turn per exchange,
    carrying the raw pipeline dicts as its text.
    """
    exporter, provider = traced_stack
    msg = "I have a headache"

    set_root_trace_id("cc" * 32)
    try:
        with _sdk_endpoint_span(provider) as endpoint_span:
            attrs = ConversationContext.SpanAttributes
            endpoint_span.set_attribute(attrs.IS_TURN_ROOT, True)
            endpoint_span.set_attribute(attrs.CONVERSATION_ID, "conv-1")
            # What RhesisTracing.start_conversation() does in app.py.
            with rhesis_invocation_context({"session_id": "conv-1"}):
                run_turn(msg, VisitPrepState(), pipeline=make_pipeline(gather_script(msg)))
    finally:
        set_root_trace_id(None)

    spans = list(exporter.get_finished_spans())
    endpoint = next(s for s in spans if s.name == "function.visit_prep_chat")
    pipeline_span = next(s for s in spans if s.name == "function.haystack.pipeline.run")
    span_attrs = ConversationContext.SpanAttributes

    assert pipeline_span.parent is not None
    assert pipeline_span.parent.span_id == endpoint.context.span_id
    assert span_attrs.IS_TURN_ROOT not in pipeline_span.attributes
    assert span_attrs.CONVERSATION_INPUT not in pipeline_span.attributes
    assert span_attrs.CONVERSATION_OUTPUT not in pipeline_span.attributes
    # Session grouping still reaches the Haystack span.
    assert pipeline_span.attributes[span_attrs.CONVERSATION_ID] == "conv-1"

    converted = RhesisOTLPExporter(
        api_key="test-key",
        base_url="http://localhost:8080",
        project_id="proj-test",
        environment="test",
    )._convert_spans(spans)
    roots = [s.span_name for s in converted.spans if s.parent_span_id is None]
    assert roots == ["function.visit_prep_chat"]
    assert all(s.conversation_id == "conv-1" for s in converted.spans)


@pytest.mark.parametrize(
    ("label", "message", "script_factory", "expected_reply"),
    [
        (
            "gathering",
            "I have a headache",
            lambda msg: gather_script(msg),
            "Where is the pain located?",
        ),
        # A terminal tool ends the run on a TOOL message, so the reply is a tool result
        # rather than assistant text — the case a generic extractor gets wrong.
        ("terminal tool", "hello", lambda msg: greeting_script(), None),
    ],
)
def test_traced_turn_owns_the_conversation_turn(
    script_tracing, label, message, script_factory, expected_reply
):
    """A script turn must publish the message and the reply, not the pipeline dicts.

    Regression guard for the traced scripts: with no SDK ``@endpoint`` above it, the Haystack
    ``pipeline.run`` span used to claim the turn and stamp ``json.dumps`` of the whole pipeline
    input/output as the conversation text.
    """
    exporter, tracing_instance = script_tracing
    attrs = ConversationContext.SpanAttributes

    tracing_instance.start_conversation("script-session")
    with tracing_instance.turn(message) as turn:
        result = run_turn(
            message, VisitPrepState(), pipeline=make_pipeline(script_factory(message))
        )
        turn.output = result["response"]

    spans = list(exporter.get_finished_spans())
    roots = [s for s in spans if s.attributes.get(attrs.IS_TURN_ROOT)]
    assert [s.name for s in roots] == [TURN_SPAN_NAME], label

    root = roots[0]
    assert root.attributes[attrs.CONVERSATION_INPUT] == message
    assert root.attributes[attrs.CONVERSATION_OUTPUT] == result["response"]
    assert root.attributes[attrs.CONVERSATION_ID] == "script-session"
    if expected_reply is not None:
        assert result["response"] == expected_reply

    # The conversation text must never be a serialized pipeline payload. Scoped to the
    # conversation attributes: haystack.pipeline.input_data legitimately holds that dict.
    for key in (attrs.CONVERSATION_INPUT, attrs.CONVERSATION_OUTPUT):
        assert '{"coordinator":' not in root.attributes[key]

    # The Haystack root defers: no turn-root flag, no restated conversation I/O.
    pipeline_span = next(s for s in spans if s.name == "function.haystack.pipeline.run")
    assert attrs.IS_TURN_ROOT not in pipeline_span.attributes
    assert attrs.CONVERSATION_INPUT not in pipeline_span.attributes
    assert attrs.CONVERSATION_OUTPUT not in pipeline_span.attributes
    assert pipeline_span.parent.span_id == root.context.span_id


def test_conversation_turns_share_one_trace(script_tracing):
    """Every turn of a conversation belongs to one trace, and the agent spans join it.

    The mechanism is covered in the integration's own tests; this checks visit-prep wires it
    up, so the whole exchange can be read as a single trace.
    """
    exporter, tracing_instance = script_tracing
    attrs = ConversationContext.SpanAttributes

    tracing_instance.start_conversation("conv-a")
    state = VisitPrepState()
    for message in ["dull headache", "three days ago", "both temples"]:
        with tracing_instance.turn(message) as turn:
            result = run_turn(message, state, pipeline=make_pipeline(gather_script(message)))
            turn.output = result["response"]
        state = result["state"]

    spans = list(exporter.get_finished_spans())
    assert len({format(s.context.trace_id, "032x") for s in spans}) == 1, (
        "turns and their agent spans must all share the conversation trace"
    )
    assert len([s for s in spans if s.attributes.get(attrs.IS_TURN_ROOT)]) == 3

    # Turns stay root spans: the exporter strips the synthetic parent that carried the trace id.
    converted = RhesisOTLPExporter(
        api_key="test-key",
        base_url="http://localhost:8080",
        project_id="proj-test",
        environment="test",
    )._convert_spans(spans)
    turn_roots = [s for s in converted.spans if s.span_name == TURN_SPAN_NAME]
    assert len(turn_roots) == 3
    assert all(s.parent_span_id is None for s in turn_roots)
    assert all(s.conversation_id == "conv-a" for s in converted.spans)
