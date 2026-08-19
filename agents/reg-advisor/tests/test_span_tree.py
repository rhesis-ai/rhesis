"""Guard the shape of the Rhesis trace produced by a real Reg-Advisor turn.

The test that catches a refactor silently flattening the agent graph. It drives
the real coordinator with the mocked model, translates the spans through the real
``GoogleADKIntegration``, and asserts on what comes out.

Why it needs to exist: Reg-Advisor delegates through ``AgentTool``, which nests a
whole inner ADK ``Runner`` under an ``execute_tool`` span. There is no
``transfer_to_agent`` anywhere in this app, so the *only* thing producing the
agent-to-agent edges the Rhesis Graph View draws is the SDK's synthesis of
``ai.agent.handoff`` spans from that nesting. If the nesting changes, the graph
goes flat and nothing else in the suite would notice.

No network and no API key: the model is mocked all the way down.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from rhesis.sdk.telemetry.integrations.google_adk import GoogleADKIntegration
from rhesis.telemetry.attributes import AIAttributes, validate_span_name

from reg_advisor.session import StateStore, run_chat_turn
from reg_advisor.state import ProductProfile, RegAdvisorState
from tests.mocks import (
    COMPLETE_PROFILE,
    MockLlm,
    briefing_script,
    build_runner_with,
    gather_script,
)


@pytest.fixture(scope="module")
def provider_and_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Attach an in-memory exporter to the process's tracer provider.

    OTEL only honours the first ``set_tracer_provider`` call, so ride on an
    existing real provider when there is one.
    """
    captured = InMemorySpanExporter()
    existing = otel_trace.get_tracer_provider()
    if isinstance(existing, TracerProvider):
        provider: TracerProvider = existing
    else:
        provider = TracerProvider()
        otel_trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(captured))
    return provider, captured


@pytest.fixture
def spans(provider_and_exporter):
    """Enable the real integration, yield a drain callable, then tear it down."""
    provider, captured = provider_and_exporter
    integration = GoogleADKIntegration()
    assert integration.enable() is True, "the Google ADK integration must enable"
    captured.clear()

    def drain():
        provider.force_flush()
        return list(captured.get_finished_spans())

    try:
        yield drain
    finally:
        integration.disable()
        captured.clear()


def _run_gathering_turn() -> MockLlm:
    """One coordinator turn that delegates to the intake agent via AgentTool."""
    model = MockLlm(gather_script("A smartwatch app estimating AF risk from PPG."))
    run_chat_turn(
        "A smartwatch app estimating AF risk from PPG.",
        conversation_id="trace-shape-1",
        store=StateStore(),
        runner=build_runner_with(model),
    )
    return model


def _run_briefing_turn() -> MockLlm:
    """One coordinator turn that delegates twice: briefing agent, then its critic.

    A complete profile is what unlocks the briefing route; the phase is an outcome
    of the turn, not an entry condition.
    """
    store = StateStore()
    store.set("trace-shape-2", RegAdvisorState(profile=ProductProfile(**COMPLETE_PROFILE)))
    model = MockLlm(briefing_script())
    run_chat_turn(
        "Please write the briefing.",
        conversation_id="trace-shape-2",
        store=store,
        runner=build_runner_with(model),
    )
    return model


def test_agent_model_and_tool_spans_are_present(spans):
    _run_gathering_turn()
    names = {span.name for span in spans()}
    assert {"ai.agent.invoke", "ai.llm.invoke", "ai.tool.invoke"} <= names, names


def test_every_span_name_is_accepted_by_the_backend(spans):
    """A name outside ai.*/function.* is rejected with HTTP 422 and dropped."""
    _run_gathering_turn()
    offenders = [span.name for span in spans() if not validate_span_name(span.name)]
    assert offenders == []


def test_agent_graph_is_connected(spans):
    """AgentTool delegation must produce handoff edges, or the Graph View is flat."""
    _run_gathering_turn()
    edges = {
        (
            span.attributes.get(AIAttributes.AGENT_HANDOFF_FROM),
            span.attributes.get(AIAttributes.AGENT_HANDOFF_TO),
        )
        for span in spans()
        if span.name == "ai.agent.handoff"
    }
    assert ("reg_advisor_coordinator", "intake_agent") in edges, edges


def test_nested_delegation_produces_a_chain_of_edges(spans):
    """coordinator -> briefing_agent -> citation_critic, two levels deep."""
    _run_briefing_turn()
    edges = {
        (
            span.attributes.get(AIAttributes.AGENT_HANDOFF_FROM),
            span.attributes.get(AIAttributes.AGENT_HANDOFF_TO),
        )
        for span in spans()
        if span.name == "ai.agent.handoff"
    }
    assert ("reg_advisor_coordinator", "briefing_agent") in edges, edges
    assert ("briefing_agent", "citation_critic") in edges, edges


def test_model_calls_are_not_duplicated(spans):
    """ADK emits call_llm wrapping generate_content; only one may be ai.llm.invoke.

    Counted against what the mocked model actually served, so the invariant is
    "exactly one LLM span per model call" rather than a number to keep in sync.
    """
    model = _run_gathering_turn()
    emitted = [span.name for span in spans()]
    llm_spans = [name for name in emitted if name == "ai.llm.invoke"]
    assert len(llm_spans) == len(model.requests), emitted
    assert not any("generate_content" in name for name in emitted)


def test_tool_spans_keep_a_parent(spans):
    """ADK parents tool spans on the inner model span the SDK drops."""
    _run_gathering_turn()
    exported = spans()
    by_id = {span.context.span_id: span for span in exported}
    tool_spans = [span for span in exported if span.name == "ai.tool.invoke"]
    assert tool_spans, "expected at least one tool span"
    for span in tool_spans:
        assert span.parent is not None, f"{span.name} was orphaned"
        assert span.parent.span_id in by_id, f"{span.name} points at a dropped parent"


def test_turn_root_carries_the_conversation(spans):
    """A plain run must populate the Conversation tab with no manual span code."""
    from rhesis.telemetry.constants import ConversationContext

    _run_gathering_turn()
    roots = [span for span in spans() if span.parent is None]
    assert len(roots) == 1, [span.name for span in roots]
    attributes = roots[0].attributes
    assert attributes[ConversationContext.SpanAttributes.IS_TURN_ROOT] is True
    assert attributes[ConversationContext.SpanAttributes.CONVERSATION_ID] == "trace-shape-1"
    assert attributes[ConversationContext.SpanAttributes.CONVERSATION_INPUT]
    assert attributes[ConversationContext.SpanAttributes.CONVERSATION_OUTPUT]


def test_prompts_and_completions_carry_real_text(spans):
    _run_gathering_turn()
    llm_spans = [span for span in spans() if span.name == "ai.llm.invoke"]
    assert llm_spans
    event_names = {event.name for span in llm_spans for event in span.events}
    assert "ai.prompt" in event_names
    assert "ai.completion" in event_names
