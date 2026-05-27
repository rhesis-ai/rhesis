"""Tests for the OTEL ``ai.tool.invoke`` / ``ai.llm.invoke`` spans
emitted by the agent stack.

Covers three sites:

1. ``ToolExecutor.execute_tool`` (``sdk/agents/mcp/executor.py``) for
   external MCP tools.
2. ``ArchitectAgent._execute_save_plan`` / ``_execute_await_task`` for
   internal tools.
3. ``BaseAgent._get_llm_action`` for each reasoning iteration.

The fixtures install an ``InMemorySpanExporter`` against the global
tracer provider so we can assert the emitted spans without spinning up
a real backend.  ``trace.get_tracer`` returns a ``ProxyTracer`` that
defers to whatever provider is current at span-creation time, so
modules that cache a tracer at import time (which is what the agent
helpers do) still see the swapped provider.
"""

from __future__ import annotations

import json
from typing import Iterator, List
from unittest.mock import AsyncMock, Mock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from rhesis.sdk.agents.base import BaseAgent
from rhesis.sdk.agents.constants import InternalTool
from rhesis.sdk.agents.mcp.exceptions import MCPApplicationError, MCPConnectionError
from rhesis.sdk.agents.mcp.executor import ToolExecutor
from rhesis.sdk.agents.schemas import ToolCall
from rhesis.sdk.models.base import BaseLLM

# ─── tracer / exporter fixture ───────────────────────────────────────


def _rebind_module_tracers(provider: trace.TracerProvider) -> None:
    """Replace the cached tracers in modules under test so they pick up
    the fixture provider.

    ``trace.get_tracer`` returns a ``ProxyTracer`` that caches its real
    tracer on first use; once the no-op tracer is captured (which can
    happen during import-time evaluation in another test), the proxy
    never re-resolves.  Bypass that by binding a real tracer from the
    fresh provider directly.
    """
    from rhesis.sdk.agents import _tool_tracing as _tt
    from rhesis.sdk.agents import base as _ba

    _tt._tracer = provider.get_tracer("rhesis.sdk.agents.tools")
    _ba._LLM_TRACER = provider.get_tracer("rhesis.sdk.agents.llm")


@pytest.fixture
def span_exporter() -> Iterator[InMemorySpanExporter]:
    """Install an in-memory exporter against the global tracer provider.

    A fresh provider is installed for the test; the previous provider
    is restored on teardown so unrelated tests aren't affected.

    ``set_tracer_provider`` is one-shot inside the OTEL API (guarded by
    ``_TRACER_PROVIDER_SET_ONCE``), so we manipulate the underlying
    module globals directly to swap providers between tests.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    previous_provider = getattr(trace, "_TRACER_PROVIDER", None)
    trace._TRACER_PROVIDER = provider  # type: ignore[attr-defined]
    _rebind_module_tracers(provider)
    try:
        yield exporter
    finally:
        trace._TRACER_PROVIDER = previous_provider  # type: ignore[attr-defined]
        # Reset the cached tracers to the no-op state so other tests
        # observe the original behaviour.
        from opentelemetry.trace import NoOpTracerProvider

        _rebind_module_tracers(NoOpTracerProvider())


def _spans_named(exporter: InMemorySpanExporter, name: str) -> List[ReadableSpan]:
    return [s for s in exporter.get_finished_spans() if s.name == name]


# ─── MCP ToolExecutor ────────────────────────────────────────────────


def _make_mcp_result(text: str, *, is_error: bool = False) -> Mock:
    result = Mock()
    result.isError = is_error
    chunk = Mock()
    chunk.text = text
    result.content = [chunk]
    return result


@pytest.fixture
def mcp_client() -> Mock:
    client = Mock()
    client.list_tools = AsyncMock(return_value=[])
    client.call_tool = AsyncMock()
    return client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mcp_executor_emits_success_span(span_exporter, mcp_client) -> None:
    """A successful MCP call produces one ``ai.tool.invoke`` span with
    OK status and the dynamic tool name / type / input / output."""
    mcp_client.call_tool.return_value = _make_mcp_result("Found 3 results")
    executor = ToolExecutor(mcp_client)

    result = await executor.execute_tool(
        ToolCall(tool_name="search_pages", arguments={"query": "test"})
    )

    assert result.success is True

    spans = _spans_named(span_exporter, "ai.tool.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.tool.name"] == "search_pages"
    assert span.attributes["ai.tool.type"] == "mcp"
    assert span.attributes["ai.tool.success"] is True
    assert span.attributes["ai.operation.type"] == "tool.invoke"
    assert span.status.status_code == StatusCode.OK

    event_names = [e.name for e in span.events]
    assert "ai.tool.input" in event_names
    assert "ai.tool.output" in event_names
    input_event = next(e for e in span.events if e.name == "ai.tool.input")
    assert json.loads(input_event.attributes["ai.tool.input"]) == {"query": "test"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mcp_executor_marks_recoverable_failure(span_exporter, mcp_client) -> None:
    """A 4xx app-level error is recorded as a failed result with span
    status ERROR — the agent retries, so no exception is raised."""
    mcp_client.call_tool.return_value = _make_mcp_result(
        json.dumps({"status": 404, "detail": "not found"})
    )
    executor = ToolExecutor(mcp_client)

    result = await executor.execute_tool(ToolCall(tool_name="lookup", arguments={}))

    assert result.success is False

    spans = _spans_named(span_exporter, "ai.tool.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.tool.success"] is False
    assert span.attributes["ai.error.type"] == "tool_failure"
    assert span.status.status_code == StatusCode.ERROR


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mcp_executor_marks_fatal_application_error(span_exporter, mcp_client) -> None:
    """A 5xx app-level error raises ``MCPApplicationError`` AND records
    the span as ERROR with the exception attached."""
    mcp_client.call_tool.return_value = _make_mcp_result(
        json.dumps({"status": 500, "detail": "boom"})
    )
    executor = ToolExecutor(mcp_client)

    with pytest.raises(MCPApplicationError):
        await executor.execute_tool(ToolCall(tool_name="lookup", arguments={}))

    spans = _spans_named(span_exporter, "ai.tool.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.error.type"] == "mcp_application_error"
    assert span.status.status_code == StatusCode.ERROR


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mcp_executor_marks_connection_error(span_exporter, mcp_client) -> None:
    """A connection failure is translated to ``MCPConnectionError`` and
    the span records the original exception with the connection
    ``ai.error.type``."""
    mcp_client.call_tool.side_effect = ConnectionError("network down")
    executor = ToolExecutor(mcp_client)

    with pytest.raises(MCPConnectionError):
        await executor.execute_tool(ToolCall(tool_name="lookup", arguments={}))

    spans = _spans_named(span_exporter, "ai.tool.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.error.type"] == "mcp_connection_error"
    assert span.status.status_code == StatusCode.ERROR


# ─── Internal-tool tracing (architect) ───────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_internal_tool_await_task_emits_span(span_exporter) -> None:
    """``ArchitectAgent._execute_await_task`` should emit an
    ``ai.tool.invoke`` span with ``ai.tool.type == "internal"`` and the
    canonical internal-tool name."""
    # Imported here to avoid heavy import chain when the rest of the
    # module is collected.
    from rhesis.sdk.agents.architect.agent import ArchitectAgent
    from rhesis.sdk.agents.architect.config import ArchitectConfig

    model = Mock(spec=BaseLLM)
    agent = ArchitectAgent(model=model, tools=[], config=ArchitectConfig())

    tool_call = ToolCall(
        tool_name=InternalTool.AWAIT_TASK,
        arguments={"task_ids": ["abc-123"], "message": "Hold on"},
    )

    result = await agent._execute_await_task(tool_call)

    assert result.success is True

    spans = _spans_named(span_exporter, "ai.tool.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.tool.name"] == InternalTool.AWAIT_TASK
    assert span.attributes["ai.tool.type"] == "internal"
    assert span.attributes["ai.tool.success"] is True
    assert span.status.status_code == StatusCode.OK


@pytest.mark.unit
@pytest.mark.asyncio
async def test_internal_tool_await_task_marks_failure(span_exporter) -> None:
    """Missing ``task_ids`` should fail the await_task tool and mark
    the span as ERROR with the ``tool_failure`` error type."""
    from rhesis.sdk.agents.architect.agent import ArchitectAgent
    from rhesis.sdk.agents.architect.config import ArchitectConfig

    model = Mock(spec=BaseLLM)
    agent = ArchitectAgent(model=model, tools=[], config=ArchitectConfig())

    result = await agent._execute_await_task(
        ToolCall(tool_name=InternalTool.AWAIT_TASK, arguments={})
    )

    assert result.success is False

    spans = _spans_named(span_exporter, "ai.tool.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.tool.success"] is False
    assert span.attributes["ai.error.type"] == "tool_failure"
    assert span.status.status_code == StatusCode.ERROR


# ─── LLM iteration tracing ───────────────────────────────────────────


def _llm_finish_response() -> dict:
    return {
        "reasoning": "All set",
        "action": "finish",
        "tool_calls": [],
        "final_answer": "ok",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_iteration_emits_span(span_exporter) -> None:
    """Each reasoning step produces one ``ai.llm.invoke`` span with the
    model provider / name attributes and the iteration counter."""
    model = Mock(spec=BaseLLM)
    model.PROVIDER = "openai"
    model.model_name = "gpt-test"
    model.generate = Mock(return_value=_llm_finish_response())

    agent = BaseAgent(model=model, tools=[], verbose=False)
    action = await agent._get_llm_action("hello", iteration=3)

    assert action is not None
    assert action.action == "finish"

    spans = _spans_named(span_exporter, "ai.llm.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.operation.type"] == "llm.invoke"
    assert span.attributes["ai.model.provider"] == "openai"
    assert span.attributes["ai.model.name"] == "gpt-test"
    assert span.attributes["agent.iteration"] == 3
    assert span.attributes["agent.action"] == "finish"
    assert span.status.status_code == StatusCode.OK

    event_names = [e.name for e in span.events]
    assert "ai.prompt" in event_names
    assert "ai.completion" in event_names


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_iteration_marks_provider_error(span_exporter) -> None:
    """A provider-level ``{"error": ...}`` response marks the span as
    ERROR with ``provider_error`` and returns ``None`` so the agent
    surfaces the friendly capability hint."""
    model = Mock(spec=BaseLLM)
    model.PROVIDER = "openai"
    model.model_name = "gpt-test"
    model.generate = Mock(return_value={"error": "rate limited"})

    agent = BaseAgent(model=model, tools=[], verbose=False)
    action = await agent._get_llm_action("hello", iteration=1)

    assert action is None

    spans = _spans_named(span_exporter, "ai.llm.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.error.type"] == "provider_error"
    assert span.status.status_code == StatusCode.ERROR


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_iteration_marks_transport_error(span_exporter) -> None:
    """A raised exception (timeout, network, etc.) is recorded as a
    ``transport_error`` ERROR span with ``record_exception`` data."""
    model = Mock(spec=BaseLLM)
    model.PROVIDER = "openai"
    model.model_name = "gpt-test"
    model.generate = Mock(side_effect=RuntimeError("connection reset"))

    agent = BaseAgent(model=model, tools=[], verbose=False)
    action = await agent._get_llm_action("hello", iteration=1)

    assert action is None

    spans = _spans_named(span_exporter, "ai.llm.invoke")
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["ai.error.type"] == "transport_error"
    assert span.status.status_code == StatusCode.ERROR
    exception_events = [e for e in span.events if e.name == "exception"]
    assert exception_events, "expected record_exception to add an event"


# ─── no-op tracer fallback ───────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_executor_works_without_tracer_provider(mcp_client) -> None:
    """When no tracer provider is configured the spans become no-ops
    and the executor must continue to function correctly."""
    from opentelemetry.trace import NoOpTracerProvider

    noop_provider = NoOpTracerProvider()
    previous_provider = getattr(trace, "_TRACER_PROVIDER", None)
    trace._TRACER_PROVIDER = noop_provider  # type: ignore[attr-defined]
    _rebind_module_tracers(noop_provider)
    try:
        mcp_client.call_tool.return_value = _make_mcp_result("ok")
        executor = ToolExecutor(mcp_client)

        result = await executor.execute_tool(
            ToolCall(tool_name="search_pages", arguments={"query": "test"})
        )
        assert result.success is True
        assert "ok" in result.content
    finally:
        trace._TRACER_PROVIDER = previous_provider  # type: ignore[attr-defined]
        _rebind_module_tracers(NoOpTracerProvider())
