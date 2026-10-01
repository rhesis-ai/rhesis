"""Guard the shape of the Rhesis trace for one docs assistant turn.

Drives a real turn with scripted models through the real bridge (`tracing.py`) into an
in-memory exporter, and checks what comes out: only names the Rhesis backend accepts, one turn
root, and each step nested where the trace viewer expects it. No network and no keys.
"""

from __future__ import annotations

import pytest
from agents import set_trace_processors, set_tracing_disabled
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from rhesis.telemetry.attributes import AIAttributes, validate_span_name

from docs_assistant import tracing
from docs_assistant.runner import run_turn
from docs_assistant.session import TURN_SPAN_NAME, ConversationStore
from tests.mocks import ScriptedModel, fetch, models, search, submit, verdict

SCOPE = "https://docs.rhesis.ai/docs/metrics/metric-scope"


@pytest.fixture(scope="module")
def provider_and_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """OTel honours only the first global provider, so ride on one if it already exists."""
    captured = InMemorySpanExporter()
    existing = otel_trace.get_tracer_provider()
    if isinstance(existing, TracerProvider):
        provider = existing
    else:
        provider = TracerProvider()
        otel_trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(captured))
    return provider, captured


@pytest.fixture
def spans(provider_and_exporter):
    provider, captured = provider_and_exporter
    tracing.install(tracing.RhesisAgentsProcessor(provider.get_tracer("test")))
    captured.clear()

    def drain():
        provider.force_flush()
        return list(captured.get_finished_spans())

    try:
        yield drain
    finally:
        set_trace_processors([])
        set_tracing_disabled(True)
        captured.clear()


async def answered_turn(cache, settings):
    answer_model = ScriptedModel([[search("metric scope")], [fetch(SCOPE)], [submit()]])
    critic_model = ScriptedModel([[verdict(True)]])
    return await run_turn(
        "What is metric scope?",
        cache=cache,
        models=models(answer_model, critic=critic_model),
        settings=settings,
        store=ConversationStore(),
        conversation_id="trace-shape-1",
    )


def by_name(spans, name):
    return [s for s in spans if s.name == name]


def parent_of(spans, span):
    if span.parent is None:
        return None
    return next((s for s in spans if s.context.span_id == span.parent.span_id), None)


def ancestors(spans, span):
    chain, current = [], parent_of(spans, span)
    while current is not None:
        chain.append(current)
        current = parent_of(spans, current)
    return chain


async def test_every_span_name_is_accepted_by_the_backend(spans, cache, settings):
    await answered_turn(cache, settings)
    finished = spans()
    assert finished
    assert [s.name for s in finished if not validate_span_name(s.name)] == []


async def test_one_turn_is_one_tree_under_the_turn_root(spans, cache, settings):
    await answered_turn(cache, settings)
    finished = spans()
    roots = by_name(finished, TURN_SPAN_NAME)
    assert len(roots) == 1
    root = roots[0]
    assert root.attributes.get("rhesis.conversation.id") == "trace-shape-1"
    assert all(s is root or root in ancestors(finished, s) for s in finished)


async def test_agents_tools_and_checks_nest_where_expected(spans, cache, settings):
    await answered_turn(cache, settings)
    finished = spans()
    agents = {
        s.attributes.get(AIAttributes.AGENT_NAME): s for s in by_name(finished, "ai.agent.invoke")
    }
    assert set(agents) == {"docs_triage", "docs_answerer", "docs_critic"}

    tools = {
        s.attributes.get(AIAttributes.TOOL_NAME): s for s in by_name(finished, "ai.tool.invoke")
    }
    assert {"search_docs", "fetch_page", "submit_answer"} <= set(tools)
    for tool in tools.values():
        assert agents["docs_answerer"] in ancestors(finished, tool)

    llm_calls = by_name(finished, "ai.llm.invoke")
    assert len(llm_calls) == 5  # triage 1, answer 3, critic 1
    assert all(s.attributes.get(AIAttributes.LLM_TOKENS_INPUT) == 100 for s in llm_calls)

    guardrails = {
        s.attributes.get(AIAttributes.GUARDRAIL_TYPE): s for s in by_name(finished, "ai.guardrail")
    }
    assert guardrails["grounding"].attributes[AIAttributes.GUARDRAIL_RESULT] == "accepted"
    assert tools["submit_answer"] in ancestors(finished, guardrails["grounding"])
    assert guardrails["critic"].attributes[AIAttributes.GUARDRAIL_RESULT] == "approved"
    assert guardrails["grounding_backstop"].attributes[AIAttributes.GUARDRAIL_RESULT] == "passed"


async def test_the_route_decision_carries_the_outcome(spans, cache, settings):
    await answered_turn(cache, settings)
    finished = spans()
    (decision,) = by_name(finished, "function.route_decision")
    assert decision.attributes["docs_assistant.route"] == "answered"
    assert decision.attributes["docs_assistant.part_routes"] == '["answered"]'
    assert decision.attributes["docs_assistant.language"] == "en"
    (precheck,) = by_name(finished, "function.precheck")
    assert precheck.attributes["docs_assistant.result"] == "pass"


async def test_tool_content_is_recorded_as_events(spans, cache, settings):
    await answered_turn(cache, settings)
    fetch_span = next(
        s
        for s in by_name(spans(), "ai.tool.invoke")
        if s.attributes.get(AIAttributes.TOOL_NAME) == "fetch_page"
    )
    events = {e.name: e for e in fetch_span.events}
    assert "metric-scope" in events["ai.tool.input"].attributes["ai.tool.input"]
    assert "<doc url=" in events["ai.tool.output"].attributes["ai.tool.output"]


async def test_a_precheck_turn_has_no_agent_spans(spans, cache, settings):
    await run_turn("hi", cache=cache, models=models(), settings=settings)
    names = {s.name for s in spans()}
    assert TURN_SPAN_NAME in names and "function.route_decision" in names
    assert "ai.agent.invoke" not in names
