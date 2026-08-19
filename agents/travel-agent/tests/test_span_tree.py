"""Trace-shape guard: the handoff edges the Rhesis Graph View draws must survive.

This agent exists to produce multi-agent traces. MAF short-circuits ``handoff_to_*`` tool
calls, so no ``execute_tool`` span is ever emitted for them - the handoff is visible only
in the chat span's output messages, from which the SDK synthesizes ``ai.agent.handoff``
spans carrying ``from``/``to``. Those synthesized spans are the graph. If a refactor stops
the agents emitting handoff tool calls, the graph silently goes flat, and this is the test
that catches it.
"""

from __future__ import annotations

import pytest
from agent_framework.observability import OBSERVABILITY_SETTINGS, enable_instrumentation
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from rhesis.telemetry.attributes import AIAttributes

from rhesis.sdk.telemetry.integrations.agent_framework import MAFIntegration
from tests.mocks import FakeHTTP, back, call, client_for, handoff, landmarks, ok, text
from travel_agent.runner import run_turn
from travel_agent.state import TripBrief, TripLeg


@pytest.fixture(scope="module")
def provider_and_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Ride on the global provider when there is one; OTEL only honours the first install."""
    captured = InMemorySpanExporter()
    existing = otel_trace.get_tracer_provider()
    if isinstance(existing, TracerProvider):
        provider: TracerProvider = existing
    else:
        provider = TracerProvider()
        otel_trace.set_tracer_provider(provider)
    provider.add_span_processor(BatchSpanProcessor(captured))
    return provider, captured


@pytest.fixture
def spans(provider_and_exporter):
    """Enable the MAF integration and MAF's own instrumentation for one test."""
    provider, captured = provider_and_exporter
    saved = (
        OBSERVABILITY_SETTINGS.enable_instrumentation,
        OBSERVABILITY_SETTINGS.enable_sensitive_data,
    )
    integration = MAFIntegration()
    assert integration.enable() is True
    # Sensitive-data capture is what makes MAF record output messages, which is where the
    # handoff decision lives.
    enable_instrumentation(enable_sensitive_data=True)

    def drain():
        provider.force_flush()
        return list(captured.get_finished_spans())

    try:
        yield drain
    finally:
        integration.disable()
        captured.clear()
        (
            OBSERVABILITY_SETTINGS.enable_instrumentation,
            OBSERVABILITY_SETTINGS.enable_sensitive_data,
        ) = saved


async def test_handoff_emits_agent_handoff_spans_with_from_and_to(spans, monkeypatch):
    FakeHTTP({"sights": ok(landmarks("Senso-ji", "Tokyo Tower"))}).install(monkeypatch)
    brief = TripBrief(legs=[TripLeg(city="Tokyo", days=3, lat=35.68, lon=139.69)])

    await run_turn(
        brief,
        "Plan my Tokyo trip",
        client=client_for(
            handoff("sightseeing_scout"),
            call("find_sightseeing", city="Tokyo"),
            back(),
            text("Here is your 3-day Tokyo plan."),
        ),
    )

    finished = spans()
    handoffs = [s for s in finished if s.name == "ai.agent.handoff"]
    assert handoffs, f"no ai.agent.handoff span emitted; saw {sorted({s.name for s in finished})}"

    targets = {s.attributes.get(AIAttributes.AGENT_HANDOFF_TO) for s in handoffs}
    froms = {s.attributes.get(AIAttributes.AGENT_HANDOFF_FROM) for s in handoffs}
    assert "sightseeing_scout" in targets
    assert "trip_coordinator" in targets, "the specialist must hand control back"
    assert "trip_coordinator" in froms


async def test_turn_emits_the_expected_span_kinds(spans, monkeypatch):
    FakeHTTP({"sights": ok(landmarks("Senso-ji"))}).install(monkeypatch)
    brief = TripBrief(legs=[TripLeg(city="Tokyo", days=3, lat=35.68, lon=139.69)])

    await run_turn(
        brief,
        "Plan my Tokyo trip",
        client=client_for(
            handoff("sightseeing_scout"),
            call("find_sightseeing", city="Tokyo"),
            back(),
            text("Here is your plan."),
        ),
    )

    names = {s.name for s in spans()}
    assert "ai.agent.invoke" in names, "per-agent activation spans are the graph's nodes"
    assert "ai.llm.invoke" in names
    assert "ai.tool.invoke" in names, "domain tool calls must still be traced"


async def test_conversational_turn_produces_no_handoff_edges(spans):
    """A greeting should be a single-agent trace - no specialist, no edges."""
    await run_turn(
        TripBrief(),
        "Hi",
        client=client_for(call("greet_and_introduce"), text("done")),
    )

    finished = spans()
    assert [s for s in finished if s.name == "ai.agent.invoke"], "the coordinator still runs"
    assert not [s for s in finished if s.name == "ai.agent.handoff"]
