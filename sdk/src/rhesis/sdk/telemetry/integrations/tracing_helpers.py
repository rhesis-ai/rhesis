"""Shared helpers for framework telemetry integrations."""

import json
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from opentelemetry import trace
from opentelemetry.trace import INVALID_SPAN, SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.context import is_tracing_disabled

MAX_CONTENT_LENGTH = 4000
MAX_SANITIZE_DEPTH = 32
_CIRCULAR_PLACEHOLDER = "[circular reference omitted]"
_DEPTH_PLACEHOLDER = "[max depth exceeded]"
_BINARY_PLACEHOLDER = "[binary data omitted]"
_SENSITIVE_KEY_FRAGMENTS = ("password", "secret", "api_key", "apikey", "token", "authorization")
_SIGNED_URL_FRAGMENTS = ("X-Amz-Signature=", "sig=", "signature=")


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _looks_like_signed_url(value: str) -> bool:
    return any(fragment in value for fragment in _SIGNED_URL_FRAGMENTS)


def sanitize_for_tracing(value: Any, *, key: str | None = None) -> Any:
    """Replace binary, embedding, and sensitive values with safe placeholders.

    Guards against pathological inputs by limiting recursion depth and detecting
    reference cycles that would otherwise recurse forever.
    """
    return _sanitize(value, key=key, depth=0, seen=set())


def _sanitize(value: Any, *, key: str | None, depth: int, seen: set[int]) -> Any:
    if key and _is_sensitive_key(key):
        return "[redacted]"

    if isinstance(value, (bytes, bytearray, memoryview)):
        return _BINARY_PLACEHOLDER

    if hasattr(value, "_to_trace_dict"):
        try:
            return _sanitize(value._to_trace_dict(), key=key, depth=depth + 1, seen=seen)
        except Exception:
            return _BINARY_PLACEHOLDER

    type_name = type(value).__name__
    if type_name in {"ByteStream", "ImageContent", "Document", "SparseEmbedding"}:
        return f"[{type_name} omitted]"

    if isinstance(value, str):
        if _looks_like_signed_url(value):
            return "[signed url omitted]"
        return value

    if isinstance(value, list):
        if len(value) > 32 and value and all(isinstance(item, (int, float)) for item in value[:8]):
            return f"[embedding vector omitted: {len(value)} dimensions]"
        if depth >= MAX_SANITIZE_DEPTH:
            return _DEPTH_PLACEHOLDER
        return [_sanitize(item, key=None, depth=depth + 1, seen=seen) for item in value]

    if isinstance(value, dict):
        if depth >= MAX_SANITIZE_DEPTH:
            return _DEPTH_PLACEHOLDER
        obj_id = id(value)
        if obj_id in seen:
            return _CIRCULAR_PLACEHOLDER
        seen.add(obj_id)
        try:
            return {
                k: _sanitize(v, key=str(k), depth=depth + 1, seen=seen)
                for k, v in value.items()
            }
        finally:
            seen.discard(obj_id)

    if hasattr(value, "to_dict"):
        try:
            return _sanitize(value.to_dict(), key=key, depth=depth + 1, seen=seen)
        except Exception:
            return str(value)

    return value


def truncate_content(value: Any) -> str:
    """Truncate serialized content for span events."""
    safe = sanitize_for_tracing(value)
    if isinstance(safe, str):
        text = safe
    else:
        try:
            text = json.dumps(safe, default=str)
        except Exception:
            text = str(safe)
    return text[:MAX_CONTENT_LENGTH]


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
    if is_tracing_disabled() or span is INVALID_SPAN:
        return
    span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
    span.set_attribute(AIAttributes.AGENT_NAME, agent_name)
    if model:
        span.set_attribute(AIAttributes.MODEL_NAME, model)
        provider = infer_model_provider(model)
        if provider:
            span.set_attribute(AIAttributes.MODEL_PROVIDER, provider)


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
        yield INVALID_SPAN
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
    if is_tracing_disabled() or span is INVALID_SPAN:
        return
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
