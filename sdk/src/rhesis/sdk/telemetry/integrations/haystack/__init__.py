"""Haystack framework integration package.

Traces Haystack pipeline runs, component runs, agent steps and tool calls, translating them into
Rhesis ``ai.*`` / ``function.*`` spans as they are opened.

Install with::

    pip install "rhesis-sdk[haystack]"

Usage::

    import os

    # Haystack reads this once, at import time. It must be set first or spans carry no content.
    os.environ["HAYSTACK_CONTENT_TRACING_ENABLED"] = "true"

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)   # installs the tracer provider
    auto_instrument("haystack")                          # must come after the client

For a chat application that drives Haystack from its own loop and wants turns grouped into one
conversation, use :class:`RhesisTracing` instead of calling ``auto_instrument`` directly::

    from rhesis.sdk.telemetry.integrations.haystack import RhesisTracing

    tracing = RhesisTracing("My Assistant")
    tracing.start_conversation("conversation-1")
    with tracing.turn("Hello") as turn:
        turn.output = run_my_pipeline("Hello")

Relation to the upstream package: deepset's ``rhesis-haystack`` covers the same ground with a
lighter dependency footprint and adds a ``RhesisConnector`` pipeline component for YAML-serialized
pipelines. This integration ships inside the SDK instead, so it needs no second exporter and shares
the provider with ``@endpoint`` / ``@observe`` spans.

Everything except :class:`HaystackIntegration` and :func:`get_integration` is exported lazily.
``tracer.py`` subclasses Haystack base classes, so importing it eagerly would break
``rhesis.sdk.telemetry.integrations`` for anyone without haystack-ai installed.
"""

from typing import TYPE_CHECKING, Any

from rhesis.sdk.telemetry.integrations.haystack.integration import (
    DEFAULT_TRACE_NAME,
    HaystackIntegration,
    get_integration,
    get_trace_id,
    get_trace_url,
    get_tracer,
)

if TYPE_CHECKING:
    from rhesis.sdk.telemetry.integrations.haystack.conversation import (
        DEFAULT_TURN_SPAN_NAME,
        ConversationTurn,
        RhesisTracing,
    )
    from rhesis.sdk.telemetry.integrations.haystack.tracer import (
        DefaultSpanHandler,
        RhesisSpan,
        RhesisTelemetry,
        RhesisTracer,
        SpanContext,
        SpanHandler,
        build_trace_url,
        resolve_frontend_url,
        rhesis_invocation_context,
        tracing_context_var,
    )

# name -> submodule it lives in, for the lazy __getattr__ below.
_LAZY_EXPORTS = {
    "DEFAULT_TURN_SPAN_NAME": "conversation",
    "ConversationTurn": "conversation",
    "RhesisTracing": "conversation",
    "DefaultSpanHandler": "tracer",
    "RhesisSpan": "tracer",
    "RhesisTelemetry": "tracer",
    "RhesisTracer": "tracer",
    "SpanContext": "tracer",
    "SpanHandler": "tracer",
    "build_trace_url": "tracer",
    "resolve_frontend_url": "tracer",
    "rhesis_invocation_context": "tracer",
    "tracing_context_var": "tracer",
}

__all__ = [
    "DEFAULT_TRACE_NAME",
    "DEFAULT_TURN_SPAN_NAME",
    "ConversationTurn",
    "DefaultSpanHandler",
    "HaystackIntegration",
    "RhesisSpan",
    # Exported because it is the declared type of ``SpanHandler.tracer`` and of
    # ``RhesisTracer.telemetry``: a custom handler that reads ``self.tracer.otel_tracer`` or opens
    # its own span needs the type without importing a private module path.
    "RhesisTelemetry",
    "RhesisTracer",
    "RhesisTracing",
    "SpanContext",
    "SpanHandler",
    "build_trace_url",
    "get_integration",
    "get_trace_id",
    "get_trace_url",
    "get_tracer",
    "resolve_frontend_url",
    "rhesis_invocation_context",
    "tracing_context_var",
]


def __getattr__(name: str) -> Any:
    """Import the Haystack-dependent submodules only when one of their names is asked for."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    import importlib

    module = importlib.import_module(f"{__name__}.{module_name}")
    value = getattr(module, name)
    globals()[name] = value  # cache, so the next lookup skips this hook
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
