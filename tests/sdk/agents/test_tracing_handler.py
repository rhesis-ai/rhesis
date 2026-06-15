"""Tests for the agent-level ``ai.agent.invoke`` span emitted by
``rhesis.sdk.agents.tracing.TracingHandler``.

These tests assert the span shape — name, attributes, events, status —
without depending on a real LLM or MCP server.  The handler resolves
its tracer via ``RhesisClient._tracer.tracer`` (see
``TracingHandler._get_tracer``), so we patch ``get_default_client`` /
``is_client_disabled`` to return a stub client whose tracer writes to
an ``InMemorySpanExporter``.
"""

from __future__ import annotations

from typing import Iterator, List
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from rhesis.sdk.agents.schemas import AgentResult
from rhesis.sdk.agents.tracing import TracingHandler


def _make_result(
    *,
    success: bool = True,
    final_answer: str = "ok",
    error: str | None = None,
) -> AgentResult:
    """Build an ``AgentResult`` with the minimum fields needed by the
    tracing handler.  Mirrors how ``ArchitectAgent`` constructs the
    result inside ``chat_async``."""
    return AgentResult(
        final_answer=final_answer,
        iterations_used=1,
        max_iterations_reached=False,
        success=success,
        error=error,
    )


@pytest.fixture
def exporter_handler(monkeypatch) -> Iterator[tuple[InMemorySpanExporter, TracingHandler]]:
    """Wire a fresh in-memory exporter into a stub default client and
    yield it together with a ``TracingHandler`` instance that uses it.

    Using a dedicated ``TracerProvider`` per test keeps the captured
    spans isolated and avoids cross-test pollution.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("rhesis.sdk.agents.tracing.tests")

    client = MagicMock()
    client._tracer = MagicMock()
    client._tracer.tracer = tracer

    monkeypatch.setattr(
        "rhesis.sdk.decorators._state.get_default_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "rhesis.sdk.decorators._state.is_client_disabled",
        lambda: False,
    )

    handler = TracingHandler(agent_name="researcher", model_name="gpt-test")
    yield exporter, handler


def _spans_named(exporter: InMemorySpanExporter, name: str) -> List[ReadableSpan]:
    return [s for s in exporter.get_finished_spans() if s.name == name]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_span_uses_semantic_attributes(exporter_handler) -> None:
    """A successful agent run produces one ``ai.agent.invoke`` span
    stamped with ``ai.agent.name``, ``ai.operation.type``, the model
    name, plus ``ai.agent.input`` / ``ai.agent.output`` events."""
    exporter, handler = exporter_handler

    await handler.on_agent_start(query="hello agent")
    await handler.on_agent_end(result=_make_result(final_answer="hi"))

    spans = _spans_named(exporter, "ai.agent.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.operation.type"] == "agent.invoke"
    assert span.attributes["ai.agent.name"] == "researcher"
    assert span.attributes["ai.model.name"] == "gpt-test"
    assert span.status.status_code == StatusCode.OK

    event_names = [e.name for e in span.events]
    assert "ai.agent.input" in event_names
    assert "ai.agent.output" in event_names

    input_event = next(e for e in span.events if e.name == "ai.agent.input")
    assert input_event.attributes["ai.agent.input"] == "hello agent"
    output_event = next(e for e in span.events if e.name == "ai.agent.output")
    assert output_event.attributes["ai.agent.output"] == "hi"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_span_marks_failure(exporter_handler) -> None:
    """A failed run (``result.success is False``) should mark the
    agent span as ERROR and stamp ``ai.error.type`` for filtering."""
    exporter, handler = exporter_handler

    await handler.on_agent_start(query="do something")
    await handler.on_agent_end(
        result=_make_result(success=False, final_answer="", error="boom"),
    )

    spans = _spans_named(exporter, "ai.agent.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.agent.name"] == "researcher"
    assert span.attributes["ai.error.type"] == "agent_failure"
    assert span.status.status_code == StatusCode.ERROR


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_span_truncates_huge_io(exporter_handler) -> None:
    """Inputs/outputs larger than the cap should be truncated so the
    OTEL payload stays bounded."""
    exporter, handler = exporter_handler

    huge_query = "q" * 20000
    huge_answer = "a" * 20000

    await handler.on_agent_start(query=huge_query)
    await handler.on_agent_end(result=_make_result(final_answer=huge_answer))

    span = _spans_named(exporter, "ai.agent.invoke")[0]
    input_event = next(e for e in span.events if e.name == "ai.agent.input")
    output_event = next(e for e in span.events if e.name == "ai.agent.output")
    assert len(input_event.attributes["ai.agent.input"]) == 8000
    assert len(output_event.attributes["ai.agent.output"]) == 8000


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handler_noop_when_client_disabled(monkeypatch) -> None:
    """When telemetry is disabled the handler must not crash and must
    not produce any spans, regardless of the lifecycle events fired."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    monkeypatch.setattr(
        "rhesis.sdk.decorators._state.is_client_disabled",
        lambda: True,
    )

    handler = TracingHandler(agent_name="x", model_name="m")
    await handler.on_agent_start(query="anything")
    await handler.on_agent_end(result=_make_result())

    assert exporter.get_finished_spans() == ()
