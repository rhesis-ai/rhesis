"""Shared OTEL helpers for ``ai.tool.invoke`` spans across agent paths.

Both the MCP executor (``ToolExecutor.execute_tool``) and the architect's
internal-tool dispatch (``ArchitectAgent._execute_save_plan`` /
``_execute_await_task``) need to emit a span per tool call with dynamic
attributes (tool name, type, success, error preview).  The
``@observe.tool(...)`` decorator bakes ``name`` and ``tool_type`` in at
decoration time and so can't express per-call values; these helpers fill
that gap with a uniform, runtime-stamped span.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from rhesis.sdk.agents.schemas import ToolResult
from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.telemetry.schemas import AIOperationType

# Cap tool input/output content stamped on spans to avoid blowing up the
# OTEL exporter payload.  Mirrors the LangChain integration's cap so all
# tool spans hit the same ceiling regardless of integration path.
MAX_TOOL_CONTENT = 8000

_tracer = trace.get_tracer("rhesis.sdk.agents.tools")


def _preview_arguments(arguments: Any) -> str:
    """Render tool arguments as a JSON preview, falling back to ``str``."""
    try:
        return json.dumps(arguments, default=str)
    except (TypeError, ValueError):
        return str(arguments)


@contextmanager
def tool_invoke_span(
    tool_name: str,
    tool_type: str,
    arguments: Any,
    *,
    span_kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> Iterator[Span]:
    """Open an ``ai.tool.invoke`` span with the dynamic attributes set.

    Caller stamps result-derived attributes via ``stamp_tool_result`` (or
    sets status manually on exception).  When no SDK tracer provider is
    configured, ``trace.get_tracer`` returns a no-op tracer so this
    decorator becomes a cheap no-op.

    Args:
        tool_name: ``ai.tool.name`` (e.g. ``"create_project"``,
            ``"save_plan"``).
        tool_type: ``ai.tool.type`` (e.g. ``"mcp"``, ``"internal"``).
        arguments: Tool arguments captured as ``ai.tool.input`` event.
        span_kind: OTEL ``SpanKind`` (defaults to ``INTERNAL``; MCP
            callers should pass ``CLIENT`` since the MCP server is a
            distinct process).
    """
    with _tracer.start_as_current_span(
        AIOperationType.TOOL_INVOKE,
        kind=span_kind,
    ) as span:
        span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_TOOL_INVOKE)
        span.set_attribute(AIAttributes.TOOL_NAME, tool_name)
        span.set_attribute(AIAttributes.TOOL_TYPE, tool_type)
        span.add_event(
            AIEvents.TOOL_INPUT,
            {AIAttributes.TOOL_INPUT_CONTENT: _preview_arguments(arguments)[:MAX_TOOL_CONTENT]},
        )
        yield span


def stamp_tool_result(span: Span, result: ToolResult) -> None:
    """Finalise span attributes / status from a ``ToolResult``."""
    span.set_attribute("ai.tool.success", bool(result.success))
    if result.content:
        span.add_event(
            AIEvents.TOOL_OUTPUT,
            {AIAttributes.TOOL_OUTPUT_CONTENT: str(result.content)[:MAX_TOOL_CONTENT]},
        )
    if result.success:
        span.set_status(Status(StatusCode.OK))
    else:
        error_msg = str(result.error or "tool returned success=False")
        span.set_attribute(AIAttributes.ERROR_TYPE, "tool_failure")
        span.set_status(Status(StatusCode.ERROR, error_msg))


def stamp_tool_exception(
    span: Span,
    exc: BaseException,
    *,
    error_type: Optional[str] = None,
) -> None:
    """Mark a span as failed because the tool raised an exception."""
    if error_type:
        span.set_attribute(AIAttributes.ERROR_TYPE, error_type)
    span.set_status(Status(StatusCode.ERROR, str(exc)))
    span.record_exception(exc)
