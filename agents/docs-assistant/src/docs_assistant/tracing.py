"""Send OpenAI Agents SDK spans to Rhesis as OpenTelemetry spans.

The Rhesis SDK has no Agents SDK integration yet, so this module bridges the two: a
`TracingProcessor` that opens an OTel span on the Rhesis tracer provider for every Agents SDK
span and closes it when the SDK span ends. Names follow the Rhesis schema (`ai.*` /
`function.*`); the exporter drops anything else.

    agent_span            → ai.agent.invoke    (ai.agent.name)
    generation_span       → ai.llm.invoke      (model, tokens, ai.prompt / ai.completion events)
    function_span         → ai.tool.invoke     (ai.tool.name, ai.tool.input / output events)
    guardrail_span        → ai.guardrail       (type, result)
    custom "precheck"     → function.precheck
    custom "route"        → function.route_decision   (docs_assistant.* attributes)
    custom "grounding"    → ai.guardrail       (type grounding)
    custom "critic"       → ai.guardrail       (type critic)

Each span's parent is the OTel span opened for its Agents SDK parent; a span with no parent
attaches to the current OTel context, which is the turn root from `session.traced_turn`.

The only module besides the entry points that imports the Rhesis SDK. With no Rhesis
credentials nothing is installed and the Agents SDK traces nowhere.
"""

from __future__ import annotations

import json
import logging
import os
from threading import Lock
from typing import Any

from agents import set_trace_processors, set_tracing_disabled
from agents.tracing import TracingProcessor
from agents.tracing.span_data import (
    AgentSpanData,
    CustomSpanData,
    FunctionSpanData,
    GenerationSpanData,
    GuardrailSpanData,
    HandoffSpanData,
    SpanData,
)
from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode
from rhesis.sdk.telemetry.integrations.genai import content_capture_enabled
from rhesis.telemetry.attributes import AIAttributes, AIEvents

from docs_assistant.models import configure_sdk, provider_name

logger = logging.getLogger(__name__)

TRACER_NAME = "docs_assistant"
MAX_CONTENT_CHARS = 10_000
CUSTOM_NAMES = {
    "precheck": "function.precheck",
    "route": "function.route_decision",
    "grounding": "ai.guardrail",
    "critic": "ai.guardrail",
}
GUARDRAIL_CUSTOM = {"grounding", "critic"}


def rhesis_configured() -> bool:
    return bool(os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"))


def install(processor: TracingProcessor | None = None) -> bool:
    """Route Agents SDK spans to Rhesis. Call after the Rhesis client has installed its tracer
    provider. Without credentials (and no explicit processor) nothing changes."""
    if processor is None and not rhesis_configured():
        return False
    configure_sdk()
    set_trace_processors([processor or RhesisAgentsProcessor()])
    set_tracing_disabled(False)
    return True


class RhesisAgentsProcessor(TracingProcessor):
    def __init__(self, tracer: otel_trace.Tracer | None = None) -> None:
        self._tracer = tracer or otel_trace.get_tracer(TRACER_NAME)
        self._open: dict[str, otel_trace.Span] = {}
        # Spans with no Rhesis equivalent (the SDK's task and turn spans) are skipped; their
        # children attach to the nearest mapped ancestor instead.
        self._skipped: dict[str, otel_trace.Span | None] = {}
        self._lock = Lock()
        self._capture = content_capture_enabled()

    def on_trace_start(self, trace) -> None:
        # The turn root comes from session.traced_turn, not from the Agents SDK trace.
        pass

    def on_trace_end(self, trace) -> None:
        pass

    def on_span_start(self, span) -> None:
        name = span_name(span.span_data)
        with self._lock:
            parent = self._parent(span.parent_id)
            if name is None:
                self._skipped[span.span_id] = parent
                return
        context = otel_trace.set_span_in_context(parent) if parent is not None else None
        otel_span = self._tracer.start_span(name, context=context)
        with self._lock:
            self._open[span.span_id] = otel_span

    def _parent(self, span_id: str | None) -> otel_trace.Span | None:
        if not span_id:
            return None
        return self._open.get(span_id) or self._skipped.get(span_id)

    def on_span_end(self, span) -> None:
        with self._lock:
            self._skipped.pop(span.span_id, None)
            otel_span = self._open.pop(span.span_id, None)
        if otel_span is None:
            return
        try:
            otel_span.set_attributes(span_attributes(span.span_data))
            if self._capture:
                for event_name, attributes in span_events(span.span_data):
                    otel_span.add_event(event_name, attributes)
            if span.error:
                message = str(span.error.get("message", "error"))
                otel_span.set_status(Status(StatusCode.ERROR, message))
                otel_span.set_attribute(AIAttributes.ERROR_TYPE, message[:200])
        except Exception:
            logger.warning("Could not map an Agents SDK span to Rhesis", exc_info=True)
        finally:
            otel_span.end()

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass


def span_name(data: SpanData) -> str | None:
    match data:
        case AgentSpanData():
            return "ai.agent.invoke"
        case GenerationSpanData():
            return "ai.llm.invoke"
        case FunctionSpanData():
            return "ai.tool.invoke"
        case GuardrailSpanData():
            return "ai.guardrail"
        case HandoffSpanData():
            return "ai.agent.handoff"
        case CustomSpanData():
            return CUSTOM_NAMES.get(data.name, f"function.{data.name}")
    return None


def span_attributes(data: SpanData) -> dict[str, Any]:
    match data:
        case AgentSpanData():
            return {
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_INVOKE,
                AIAttributes.AGENT_NAME: data.name,
            }
        case GenerationSpanData():
            return _generation_attributes(data)
        case FunctionSpanData():
            return {
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
                AIAttributes.TOOL_NAME: data.name,
                AIAttributes.TOOL_TYPE: "function",
            }
        case GuardrailSpanData():
            return _guardrail(data.name, "triggered" if data.triggered else "passed")
        case HandoffSpanData():
            return {
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_HANDOFF,
                AIAttributes.AGENT_HANDOFF_FROM: data.from_agent or "",
                AIAttributes.AGENT_HANDOFF_TO: data.to_agent or "",
            }
        case CustomSpanData():
            return _custom_attributes(data)
    return {}


def _generation_attributes(data: GenerationSpanData) -> dict[str, Any]:
    usage = data.usage or {}
    tokens_in = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    tokens_out = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    try:
        provider = provider_name()
    except RuntimeError:
        provider = "unknown"
    return {
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
        AIAttributes.MODEL_PROVIDER: provider,
        AIAttributes.MODEL_NAME: str(data.model or ""),
        AIAttributes.LLM_TOKENS_INPUT: tokens_in,
        AIAttributes.LLM_TOKENS_OUTPUT: tokens_out,
        AIAttributes.LLM_TOKENS_TOTAL: tokens_in + tokens_out,
    }


def _guardrail(kind: str, result: str) -> dict[str, Any]:
    return {
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_GUARDRAIL,
        AIAttributes.GUARDRAIL_TYPE: kind,
        AIAttributes.GUARDRAIL_PROVIDER: "docs_assistant",
        AIAttributes.GUARDRAIL_RESULT: result,
    }


def _custom_attributes(data: CustomSpanData) -> dict[str, Any]:
    attributes = {f"docs_assistant.{k}": _attribute_value(v) for k, v in (data.data or {}).items()}
    if data.name in GUARDRAIL_CUSTOM:
        attributes |= _guardrail(data.name, str((data.data or {}).get("result", "")))
    return attributes


def _attribute_value(value: Any) -> Any:
    if isinstance(value, (str, bool, int, float)):
        return value
    return json.dumps(value, default=str)


def span_events(data: SpanData) -> list[tuple[str, dict[str, Any]]]:
    match data:
        case GenerationSpanData():
            return [
                (AIEvents.PROMPT, {AIAttributes.PROMPT_CONTENT: _content(data.input)}),
                (AIEvents.COMPLETION, {AIAttributes.COMPLETION_CONTENT: _content(data.output)}),
            ]
        case FunctionSpanData():
            return [
                (AIEvents.TOOL_INPUT, {AIAttributes.TOOL_INPUT_CONTENT: _content(data.input)}),
                (AIEvents.TOOL_OUTPUT, {AIAttributes.TOOL_OUTPUT_CONTENT: _content(data.output)}),
            ]
    return []


def _content(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return (text or "")[:MAX_CONTENT_CHARS]
