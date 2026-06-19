"""Shared helpers for framework telemetry integrations."""

import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.context import is_tracing_disabled
from rhesis.sdk.telemetry.utils.token_extraction import extract_token_usage

MAX_CONTENT_LENGTH = 4000


def truncate_content(value: Any) -> str:
    """Truncate serialized content for span events."""
    return str(value)[:MAX_CONTENT_LENGTH]


def infer_model_provider(model_name: str) -> Optional[str]:
    """Infer provider name from a model identifier."""
    lowered = model_name.lower()
    if "gpt" in lowered or lowered.startswith("o1") or lowered.startswith("o3"):
        return "openai"
    if "claude" in lowered:
        return "anthropic"
    if "gemini" in lowered:
        return "google"
    return None


def set_agent_attributes(span: trace.Span, *, agent_name: str, model: Optional[str] = None) -> None:
    """Set common agent invocation attributes on a span."""
    span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
    span.set_attribute(AIAttributes.AGENT_NAME, agent_name)
    if model:
        span.set_attribute(AIAttributes.MODEL_NAME, model)
        provider = infer_model_provider(model)
        if provider:
            span.set_attribute(AIAttributes.MODEL_PROVIDER, provider)


def set_token_attributes(span: trace.Span, usage: Any) -> None:
    """Extract token usage from a provider response and set span attributes."""
    if usage is None:
        return
    try:
        prompt, completion, total = extract_token_usage(usage)
        span.set_attribute(AIAttributes.LLM_TOKENS_INPUT, prompt)
        span.set_attribute(AIAttributes.LLM_TOKENS_OUTPUT, completion)
        span.set_attribute(AIAttributes.LLM_TOKENS_TOTAL, total)
    except Exception:
        return


@contextmanager
def observe_framework_call(
    span_name: str,
    *,
    framework: str,
    operation_type: str = AIAttributes.OPERATION_AGENT_INVOKE,
    attributes: Optional[dict[str, Any]] = None,
) -> Iterator[trace.Span]:
    """Create a span for a framework operation with latency and error handling."""
    if is_tracing_disabled():
        yield trace.get_current_span()
        return

    tracer = trace.get_tracer(f"rhesis.sdk.integrations.{framework}")
    start = time.perf_counter()
    with tracer.start_as_current_span(span_name, kind=SpanKind.CLIENT) as span:
        span.set_attribute(AIAttributes.OPERATION_TYPE, operation_type)
        span.set_attribute(AIAttributes.SYSTEM, framework)
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("ai.operation.duration_ms", duration_ms)


def add_agent_io_events(span: trace.Span, input_data: Any, output_data: Any) -> None:
    """Record agent input/output as span events."""
    if input_data is not None:
        span.add_event(
            AIEvents.AGENT_INPUT,
            {AIAttributes.AGENT_INPUT_CONTENT: truncate_content(input_data)},
        )
    if output_data is not None:
        span.add_event(
            AIEvents.AGENT_OUTPUT,
            {AIAttributes.AGENT_OUTPUT_CONTENT: truncate_content(output_data)},
        )
