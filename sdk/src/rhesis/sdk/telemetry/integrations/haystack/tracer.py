"""Rhesis tracing bridge for Haystack.

Haystack does not emit OpenTelemetry spans on its own -- it has its own tracing abstraction and
you register an implementation with ``haystack.tracing.enable_tracing``. This module is that
implementation: :class:`RhesisTracer` and :class:`RhesisSpan` translate Haystack's span API into
Rhesis ``ai.*`` / ``function.*`` spans as they are opened, so there is nothing to translate
afterwards.

Set ``HAYSTACK_CONTENT_TRACING_ENABLED=true`` **before importing Haystack** to capture
input/output content on spans. Haystack reads that variable once, at import time, so an
integration can only warn when it is off -- never fix it.

This module imports Haystack at module level, because :class:`RhesisSpan` and
:class:`RhesisTracer` subclass Haystack base classes. Import it lazily from anywhere that must
keep working without Haystack installed.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from haystack import default_from_dict, default_to_dict
from haystack.dataclasses import ChatMessage
from haystack.tracing import Span, Tracer
from haystack.tracing import tracer as proxy_tracer
from haystack.tracing import utils as tracing_utils
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

from rhesis.sdk.telemetry.integrations.genai import (
    DISABLE_CONTENT_CAPTURE_ENV,
    TRUTHY_ENV_VALUES,
    content_capture_enabled,
)
from rhesis.sdk.telemetry.integrations.haystack import extraction, mapping
from rhesis.telemetry.attributes import MAX_CONTENT_LENGTH, AIAttributes, AIEvents
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import get_root_trace_id
from rhesis.telemetry.schemas import AIOperationType
from rhesis.telemetry.token_extraction import extract_token_usage

logger = logging.getLogger(__name__)

ENFORCE_FLUSH_ENV_VAR = "RHESIS_HAYSTACK_ENFORCE_FLUSH"
# The name the upstream ``rhesis-haystack`` package uses. Honoured so a config written against
# that package keeps working after switching to the native integration.
LEGACY_ENFORCE_FLUSH_ENV_VAR = "HAYSTACK_RHESIS_ENFORCE_FLUSH"

# Two bounds, deliberately: MAX_CONTENT_LENGTH is the framework-agnostic cap on span-event content
# shared with every other Rhesis integration, while ConversationContext.MAX_IO_LENGTH is the
# backend's own limit for the ``rhesis.conversation.*`` columns. Neither is redefined here, so
# raising either one upstream takes effect without an edit in this module.

# Root span plus the top-level agent span; anything deeper is a nested agent turn.
_OUTERMOST_AGENT_STACK_DEPTH = 2

tracing_context_var: ContextVar[dict[Any, Any]] = ContextVar("rhesis_tracing_context")
span_stack_var: ContextVar[list[RhesisSpan] | None] = ContextVar("rhesis_span_stack", default=None)
# Context-local, not tracer state: one tracer is installed process-wide via
# ``tracing.enable_tracing``, so instance state here would hand one request another request's
# trace id and deep link under concurrent runs (hayhooks, FastAPI, AsyncPipeline).
trace_id_var: ContextVar[str] = ContextVar("rhesis_trace_id", default="")


def enforce_flush_enabled() -> bool:
    """Whether to force-flush once per run, as the root span closes.

    Defaults to on: it costs one blocking round trip per run and guarantees everything is on the
    backend by the time ``run()`` returns, which is what you want for hard kills (``os._exit``,
    ``SIGKILL``, container OOM) and serverless sandbox freezes. Turn it off to leave exporting to
    the batch processor when a normal exit is guaranteed.
    """
    raw = os.getenv(ENFORCE_FLUSH_ENV_VAR)
    if raw is None:
        raw = os.getenv(LEGACY_ENFORCE_FLUSH_ENV_VAR)
    if raw is None:
        return True
    return raw.strip().lower() in TRUTHY_ENV_VALUES


def capture_content() -> bool:
    """Whether span content may be recorded.

    Two independent switches, and both must allow it: Haystack's own
    ``HAYSTACK_CONTENT_TRACING_ENABLED`` (without which Haystack never hands us content in the
    first place) and Rhesis's ``RHESIS_DISABLE_CONTENT_CAPTURE``, which every other Rhesis
    integration honours and which therefore has to work here too.
    """
    return proxy_tracer.is_content_tracing_enabled and content_capture_enabled()


@contextmanager
def rhesis_invocation_context(invocation_context: dict[str, Any] | None = None) -> Iterator[None]:
    """Attach Rhesis session/test metadata for the current async task or thread."""
    token = tracing_context_var.set(invocation_context or {})
    try:
        yield
    finally:
        tracing_context_var.reset(token)


def _is_outermost_agent_turn_span() -> bool:
    """True for the top-level agent span in a hayhooks/pipeline request."""
    stack = span_stack_var.get() or []
    return len(stack) <= _OUTERMOST_AGENT_STACK_DEPTH


def _external_turn_root_active() -> bool:
    """
    True when a Rhesis SDK span already owns the conversation turn.

    ``get_root_trace_id`` is a ``ContextVar`` the SDK tracer sets when it opens the root span of an
    ``@endpoint`` / ``@observe`` call, so it is visible to everything that call runs -- including
    the Haystack pipeline it invokes. Exactly one span per turn may carry ``is_turn_root``: the
    outermost one. When the SDK already opened it, the Haystack root span is a child of that turn,
    not a turn of its own, and must not claim the flag or restate the turn's input/output.

    Deliberately keyed on the SDK context rather than ``trace.get_current_span()``: only a span
    that actually claims the turn should suppress the flag, so unrelated ambient instrumentation
    (an HTTP server span, say) cannot leave a turn with no root at all.
    """
    return get_root_trace_id() is not None


def _apply_invocation_context(otel_span: trace.Span, *, is_turn_root: bool) -> None:
    """
    Stamp the mapped ``invocation_context`` on a span.

    Only the outermost span in a turn may carry the turn-root flag; on any other span the exporter
    would strip its real parent and detach the subtree into a turn of its own.
    """
    mapped = mapping.map_invocation_context(tracing_context_var.get({}))
    if not is_turn_root:
        # Session, conversation and test ids stay -- filtering child spans by them is the point.
        mapped.pop(ConversationContext.SpanAttributes.IS_TURN_ROOT, None)
    for key, value in mapped.items():
        otel_span.set_attribute(key, _coerce_attribute_value(value))


def _stamp_conversation_io(otel_span: trace.Span, conv_input: str, conv_output: str) -> None:
    if conv_input:
        otel_span.set_attribute(
            ConversationContext.SpanAttributes.CONVERSATION_INPUT,
            conv_input[: ConversationContext.MAX_IO_LENGTH],
        )
    if conv_output:
        otel_span.set_attribute(
            ConversationContext.SpanAttributes.CONVERSATION_OUTPUT,
            conv_output[: ConversationContext.MAX_IO_LENGTH],
        )


def resolve_frontend_url(base_url: str, frontend_url: str | None) -> str:
    """
    Resolve the Rhesis frontend base URL for trace deep links.

    Only the two well-known deployments are derived from ``base_url``. Any other backend returns
    an empty string -- and therefore an empty ``trace_url`` -- unless ``RHESIS_FRONTEND_URL`` is
    set.
    """
    if frontend_url:
        return frontend_url.rstrip("/")
    normalized = (base_url or "").rstrip("/")
    if normalized in ("http://localhost:8080", "http://127.0.0.1:8080"):
        return "http://localhost:3000"
    if normalized == "https://api.rhesis.ai":
        return "https://app.rhesis.ai"
    return ""


def build_trace_url(frontend_url: str, trace_id: str, project_id: str | None) -> str:
    """Build a frontend deep link for the given trace."""
    if not frontend_url or not trace_id:
        return ""
    params: dict[str, str] = {"open_trace": trace_id}
    if project_id:
        params["project_id"] = project_id
    return f"{frontend_url}/traces?{urlencode(params)}"


@dataclass
class RhesisTelemetry:
    """The OTel provider and tracer this integration opens spans through.

    Unlike the upstream ``rhesis-haystack`` package, this does not build a provider. The SDK's
    ``RhesisClient`` already installs one as the OpenTelemetry global, and reusing it is what makes
    a Haystack pipeline running inside an ``@endpoint`` span nest under it and flush with it.
    """

    provider: TracerProvider
    otel_tracer: trace.Tracer
    project_id: str | None
    environment: str
    base_url: str
    frontend_url: str | None = None

    def __post_init__(self) -> None:
        """Resolve ``frontend_url`` once, so readers never have to wonder whether it is raw."""
        self.frontend_url = resolve_frontend_url(self.base_url, self.frontend_url)

    def flush(self) -> None:
        """Flush pending spans to the Rhesis backend."""
        try:
            self.provider.force_flush(timeout_millis=30_000)
        except Exception as exc:  # noqa: BLE001 - tracing must never break the application
            logger.warning("Failed to flush Rhesis traces: %s", exc)


class RhesisSpan(Span):
    """Bridge between Haystack's span API and OpenTelemetry spans for Rhesis."""

    def __init__(
        self, context_manager: AbstractContextManager[Any], operation_name: str = ""
    ) -> None:
        self._span = context_manager.__enter__()
        self._data: dict[str, Any] = {}
        self._context_manager = context_manager
        # Retained so post-run enrichment can tell Haystack 3.0 agent-loop spans apart: they share
        # the same (absent) component type, so operation name is the only discriminator available.
        self.operation_name = operation_name
        # Whether this span may claim the conversation turn. Decided once at creation (see
        # DefaultSpanHandler.create_span) because by enrichment time this span is the current one
        # and the enclosing context can no longer be inspected. Defaults to True: standalone
        # Haystack, with nothing above it, owns the turn.
        self.owns_conversation_turn = True
        # Recorded at creation for the same reason: the enrichment phase needs to know whether this
        # span is the trace root, and SpanContext is no longer in scope by then.
        self.is_root = False

    def set_tag(self, key: str, value: Any) -> None:
        """Set a generic tag for this span."""
        coerced_value = tracing_utils.coerce_tag_value(value)
        # Haystack hands pipeline I/O over as an ordinary tag rather than a content tag, so it
        # arrives here whole and uncapped -- a RAG run with real documents produced a
        # 60 000-character attribute. Cap it to the same bound as content events. ``_data`` keeps
        # the full structured value, which is what the conversation-text extraction reads.
        if key in (mapping.PIPELINE_INPUT, mapping.PIPELINE_OUTPUT) and isinstance(
            coerced_value, str
        ):
            coerced_value = coerced_value[:MAX_CONTENT_LENGTH]
        self._span.set_attribute(key, _coerce_attribute_value(coerced_value))
        self._data[key] = value

    def set_content_tag(self, key: str, value: Any) -> None:
        """Set a content-specific tag for this span when content tracing is enabled."""
        if not capture_content():
            return

        self._data[key] = value

        if key.endswith(".input"):
            self._set_input_content(key, value)
        elif key.endswith(".output"):
            self._set_output_content(key, value)

    def _set_input_content(self, key: str, value: Any) -> None:
        if key == mapping.AGENT_INPUT:
            text = _stringify_content(value)
            if text:
                self._span.set_attribute(
                    AIAttributes.AGENT_INPUT_CONTENT, text[: ConversationContext.MAX_IO_LENGTH]
                )
                self._span.add_event(
                    AIEvents.AGENT_INPUT,
                    {AIAttributes.AGENT_INPUT_CONTENT: text[:MAX_CONTENT_LENGTH]},
                )
            return

        # Tool arguments are not a prompt, so they get the tool content attribute rather than
        # ai.prompt events.
        if key == mapping.AGENT_STEP_TOOL_INPUT:
            text = _stringify_content(value)
            if text:
                self._span.set_attribute(AIAttributes.TOOL_INPUT_CONTENT, text[:MAX_CONTENT_LENGTH])
            return

        if isinstance(value, dict) and "messages" in value:
            messages = [
                m.to_openai_dict_format(require_tool_call_ids=False)
                for m in (value.get("messages") or [])
            ]
            payload: Any
            if isinstance(gen_kwargs := value.get("generation_kwargs"), dict):
                payload = {"messages": messages, "generation_kwargs": gen_kwargs}
            else:
                payload = messages
            self._add_prompt_events(payload)
            return

        self._add_prompt_events(tracing_utils.coerce_tag_value(value))

    def _set_output_content(self, key: str, value: Any) -> None:
        if key == mapping.AGENT_OUTPUT:
            text = _stringify_content(value)
            if text:
                self._span.set_attribute(
                    AIAttributes.AGENT_OUTPUT_CONTENT, text[: ConversationContext.MAX_IO_LENGTH]
                )
                self._span.add_event(
                    AIEvents.AGENT_OUTPUT,
                    {AIAttributes.AGENT_OUTPUT_CONTENT: text[:MAX_CONTENT_LENGTH]},
                )
            return

        if key == mapping.AGENT_STEP_TOOL_OUTPUT:
            text = _stringify_content(value)
            if text:
                self._span.set_attribute(
                    AIAttributes.TOOL_OUTPUT_CONTENT, text[:MAX_CONTENT_LENGTH]
                )
            return

        if isinstance(value, dict) and "replies" in value:
            replies_list = value.get("replies") or []
            if all(isinstance(r, ChatMessage) for r in replies_list):
                replies = [
                    m.to_openai_dict_format(require_tool_call_ids=False) for m in replies_list
                ]
            else:
                replies = replies_list
            self._add_completion_events(replies)
            return

        self._add_completion_events(tracing_utils.coerce_tag_value(value))

    def _add_prompt_events(self, payload: Any) -> None:
        # A bare list is handled as well as the ``{"messages": [...]}`` envelope, so a prompt
        # expands to one event per message either way -- matching ``_add_completion_events``.
        # Upstream only expanded the envelope form, which meant a generator called without
        # ``generation_kwargs`` reported its whole message list as one roleless event.
        messages = payload.get("messages") if isinstance(payload, dict) else payload
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                self._span.add_event(
                    AIEvents.PROMPT,
                    {
                        AIAttributes.PROMPT_ROLE: message.get("role", "user"),
                        AIAttributes.PROMPT_CONTENT: str(message.get("content", ""))[
                            :MAX_CONTENT_LENGTH
                        ],
                    },
                )
            return
        self._span.add_event(
            AIEvents.PROMPT,
            {AIAttributes.PROMPT_CONTENT: str(payload)[:MAX_CONTENT_LENGTH]},
        )

    def _add_completion_events(self, payload: Any) -> None:
        if isinstance(payload, list):
            for item in payload:
                content = item.get("content", item) if isinstance(item, dict) else item
                self._span.add_event(
                    AIEvents.COMPLETION,
                    {AIAttributes.COMPLETION_CONTENT: str(content)[:MAX_CONTENT_LENGTH]},
                )
            return
        self._span.add_event(
            AIEvents.COMPLETION,
            {AIAttributes.COMPLETION_CONTENT: str(payload)[:MAX_CONTENT_LENGTH]},
        )

    def raw_span(self) -> trace.Span:
        """Return the underlying OpenTelemetry span instance."""
        return self._span

    def close(self, exc_info: tuple[Any, Any, Any] | None = None) -> None:
        """
        End the underlying OpenTelemetry span.

        :param exc_info: The ``sys.exc_info()`` triple when the span is closing because of an
            exception, so the context manager sees it; ``None`` on the success path.
        """
        if self._context_manager is not None:
            self._context_manager.__exit__(*(exc_info or (None, None, None)))

    def get_data(self) -> dict[str, Any]:
        """Return the raw Haystack tag data collected for this span."""
        return self._data

    def get_correlation_data_for_logs(self) -> dict[str, Any]:
        """Return trace and span identifiers for log correlation."""
        try:
            ctx = self._span.get_span_context()
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
        except (AttributeError, TypeError):
            return {}

    def set_tags(self, tags: dict[str, Any]) -> None:
        """Set multiple tags on this span."""
        for key, value in tags.items():
            self.set_tag(key, value)


@dataclass(frozen=True)
class SpanContext:
    """Context for creating spans in Rhesis."""

    name: str
    operation_name: str
    component_type: str | None
    tags: dict[str, Any]
    parent_span: Span | None
    trace_name: str = "Haystack"
    is_root: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Span name cannot be empty")
        if not self.operation_name:
            raise ValueError("Operation name cannot be empty")
        if not self.trace_name:
            raise ValueError("Trace name cannot be empty")


class SpanHandler(ABC):
    """Extension point for customizing Rhesis span creation and enrichment.

    Subclass :class:`DefaultSpanHandler` and override :meth:`handle` to redact content before it
    leaves the process, or to add attributes of your own.
    """

    def __init__(self) -> None:
        self.tracer: RhesisTelemetry | None = None

    def init_tracer(self, tracer: RhesisTelemetry) -> None:
        """Initialize with the Rhesis telemetry wrapper."""
        self.tracer = tracer

    @abstractmethod
    def create_span(self, context: SpanContext) -> RhesisSpan:
        """Create a span of appropriate type based on the context."""

    @abstractmethod
    def handle(self, span: RhesisSpan, component_type: str | None) -> None:
        """Process a span after component execution."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpanHandler:
        """Deserialize a SpanHandler from a dictionary."""
        return default_from_dict(cls, data)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this SpanHandler to a dictionary."""
        return default_to_dict(self)


def _coerce_attribute_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)):
        return value
    if value is None:
        return ""
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _stringify_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    coerced = tracing_utils.coerce_tag_value(value)
    if isinstance(coerced, str):
        return coerced
    try:
        return json.dumps(coerced, default=str)
    except (TypeError, ValueError):
        return str(coerced)


def _sanitize_usage_data(usage: dict[str, Any]) -> dict[str, int]:
    if not isinstance(usage, dict):
        return {}

    input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
    sanitized: dict[str, int] = {}
    if input_tokens:
        sanitized[AIAttributes.LLM_TOKENS_INPUT] = input_tokens
    if output_tokens:
        sanitized[AIAttributes.LLM_TOKENS_OUTPUT] = output_tokens
    if total_tokens:
        sanitized[AIAttributes.LLM_TOKENS_TOTAL] = total_tokens
    return sanitized


def _set_token_attributes(span: trace.Span, usage: dict[str, Any] | None) -> None:
    if not usage:
        return
    for key, value in _sanitize_usage_data(usage).items():
        span.set_attribute(key, value)


def _reply_meta(reply: Any) -> dict[str, Any]:
    """
    Return a chat reply's metadata, whether it arrived as a ``ChatMessage`` or a plain mapping.

    Component spans carry replies Haystack has already typed, but the Haystack 3.0 agent-loop LLM
    span reports whatever the generator put in its span tags, which need not be ``ChatMessage``
    instances. Reaching straight for ``.meta`` there raised ``AttributeError`` into the enrichment
    phase's catch-all, so the model name and token counts were dropped and the only trace of it
    was a generic "Error during span cleanup" warning.
    """
    meta: Any
    if isinstance(reply, ChatMessage):
        meta = reply.meta
    elif isinstance(reply, dict):
        meta = reply.get("meta")
    else:
        return {}
    return meta if isinstance(meta, dict) else {}


def _apply_chat_reply_metadata(otel_span: trace.Span, replies: list[Any]) -> None:
    """Promote model name, timing, and token usage from the first chat reply's metadata."""
    meta = _reply_meta(replies[0])
    if not meta:
        return
    completion_start_time = meta.get("completion_start_time")
    if completion_start_time:
        try:
            parsed = datetime.fromisoformat(completion_start_time)
            otel_span.set_attribute(mapping.COMPLETION_START_TIME_ATTRIBUTE, parsed.isoformat())
        except ValueError:
            logger.error("Failed to parse completion_start_time: %s", completion_start_time)
    model = meta.get("model")
    if model:
        otel_span.set_attribute(AIAttributes.MODEL_NAME, model)
    _set_token_attributes(otel_span, meta.get("usage"))


def _enclosing_agent_label(parent: RhesisSpan) -> str:
    """
    Name the agent that owns ``parent``, for the ``ai.agent.handoff.from`` attribute.

    Walks the ancestor stack outwards from ``parent``. A specialist agent is reached through the
    tool span that invoked it, so the nearest enclosing tool span names it; a top-level agent is
    reached as a pipeline component, so the nearest component name names it.
    """
    stack = span_stack_var.get() or []
    for span in reversed(stack):
        if span is parent:
            continue
        if span.operation_name == mapping.AGENT_STEP_TOOL:
            return str(span.get_data().get(mapping.TOOL_NAME, ""))
        component_name = span.get_data().get(mapping.COMPONENT_NAME)
        if component_name:
            return str(component_name)
    return ""


def _promote_tool_span_to_handoff(parent: RhesisSpan) -> str:
    """
    Re-label a tool span as an agent handoff and return the target agent's name.

    Called when an ``Agent`` starts running inside a tool invocation, which is how Haystack models
    a handoff to a specialist agent. The span is still open at this point, so renaming it is safe.
    """
    tool_name = str(parent.get_data().get(mapping.TOOL_NAME, ""))
    otel_parent = parent.raw_span()
    if hasattr(otel_parent, "update_name"):
        # ``.value``, not the member: AIOperationType is a (str, Enum), so the member renders as
        # "AIOperationType.AGENT_HANDOFF" anywhere the name is formatted into text.
        otel_parent.update_name(AIOperationType.AGENT_HANDOFF.value)
    otel_parent.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_HANDOFF)
    if tool_name:
        otel_parent.set_attribute(AIAttributes.AGENT_HANDOFF_TO, tool_name)
    handoff_from = _enclosing_agent_label(parent)
    if handoff_from:
        otel_parent.set_attribute(AIAttributes.AGENT_HANDOFF_FROM, handoff_from)
    return tool_name


class DefaultSpanHandler(SpanHandler):
    """Default Rhesis tracing behavior for Haystack pipelines."""

    def create_span(self, context: SpanContext) -> RhesisSpan:
        """Create a Rhesis span based on the given Haystack context."""
        if self.tracer is None:
            raise RuntimeError(
                "Tracer is not initialized. Make sure a RhesisClient exists and "
                "auto_instrument('haystack') was called before running a pipeline."
            )

        span_name = mapping.resolve_span_name(
            operation_name=context.operation_name,
            component_type=context.component_type,
            component_name=context.name,
            is_root=context.is_root,
        )

        parent_context = None
        if context.parent_span and isinstance(context.parent_span, RhesisSpan):
            parent_context = trace.set_span_in_context(context.parent_span.raw_span())

        span_cm = self.tracer.otel_tracer.start_as_current_span(
            name=span_name,
            context=parent_context,
            kind=trace.SpanKind.INTERNAL,
        )
        rhesis_span = RhesisSpan(span_cm, operation_name=context.operation_name)
        rhesis_span.owns_conversation_turn = not _external_turn_root_active()
        rhesis_span.is_root = context.is_root
        otel_span = rhesis_span.raw_span()

        operation_type = mapping.resolve_operation_type(span_name)
        if operation_type:
            otel_span.set_attribute(AIAttributes.OPERATION_TYPE, operation_type)

        if context.is_root:
            otel_span.set_attribute(mapping.TRACE_NAME_ATTRIBUTE, context.trace_name)
            # Covers callers that scope the context around the run with
            # rhesis_invocation_context(). handle() re-applies it when this span closes, for
            # callers that set it from inside the run.
            _apply_invocation_context(otel_span, is_turn_root=rhesis_span.owns_conversation_turn)

        # Haystack 2.x routed tool calls through a ToolInvoker component span.
        if context.component_type == "ToolInvoker":
            otel_span.set_attribute(AIAttributes.TOOL_NAME, context.name)
            otel_span.set_attribute(AIAttributes.TOOL_TYPE, "haystack")

        # Haystack 3.0 traces each tool call individually and names it in the span tags.
        if context.operation_name == mapping.AGENT_STEP_TOOL:
            tool_name = context.tags.get(mapping.TOOL_NAME)
            if tool_name:
                otel_span.set_attribute(AIAttributes.TOOL_NAME, str(tool_name))
            otel_span.set_attribute(AIAttributes.TOOL_TYPE, "haystack")

        if context.operation_name == mapping.AGENT_RUN:
            self._label_agent_span(otel_span, context)

        return rhesis_span

    @staticmethod
    def _label_agent_span(otel_span: trace.Span, context: SpanContext) -> None:
        """Name an agent span, and mark its caller as a handoff when one agent invoked another."""
        parent = context.parent_span
        if not isinstance(parent, RhesisSpan):
            return
        if parent.operation_name == mapping.AGENT_STEP_TOOL:
            agent_name = _promote_tool_span_to_handoff(parent)
        else:
            agent_name = str(parent.get_data().get(mapping.COMPONENT_NAME, ""))
        if agent_name:
            otel_span.set_attribute(AIAttributes.AGENT_NAME, agent_name)

    def handle(self, span: RhesisSpan, component_type: str | None) -> None:
        """Process and enrich a span after component execution."""
        self._apply_invocation_context(span)
        self._promote_conversation_io(span)
        self._rename_tool_invoker(span, component_type)
        self._apply_model_metadata(span, component_type)

    @staticmethod
    def _apply_invocation_context(span: RhesisSpan) -> None:
        """
        Stamp the run's ``invocation_context`` on this span.

        Applied to every span, not just the root: filtering a trace's child spans by your own run
        id or session is the reason for passing one, and on the root alone that query returns
        nothing.

        Re-read here rather than trusting what ``create_span`` saw, since a caller may set the
        context from inside the run. ``RhesisTracer.trace`` scopes the ContextVar to the run's root
        span, so what is read here belongs to this run and no other. Applied whether or not
        conversation text was found -- test-run correlation on a pipeline that carries no chat
        messages is still worth having.
        """
        _apply_invocation_context(
            span.raw_span(),
            is_turn_root=span.is_root and span.owns_conversation_turn,
        )

    @staticmethod
    def _promote_conversation_io(span: RhesisSpan) -> None:
        """
        Promote the turn's user message and reply onto ``rhesis.conversation.input``/``.output``.

        This is content tracing, so it obeys the content flags: ``span.get_data()`` is filled by
        ``set_tag`` regardless of them, so without this check a user who opted out still got their
        message on the most prominently named attribute the integration emits.

        Skipped entirely when a Rhesis SDK span owns the turn -- it already carries the mapped user
        message and reply, and restating them here produced duplicate, unreadable turns.
        """
        if not (span.owns_conversation_turn and capture_content()):
            return

        data = span.get_data()
        conv_input = ""
        conv_output = ""
        if data.get(mapping.PIPELINE_INPUT) is not None:
            conv_input, conv_output = extraction.pipeline_conversation_io(data)
        elif data.get(mapping.AGENT_INPUT) is not None and _is_outermost_agent_turn_span():
            conv_input, conv_output = extraction.agent_conversation_io(data)

        if conv_input or conv_output:
            _stamp_conversation_io(span.raw_span(), conv_input, conv_output)

    @staticmethod
    def _rename_tool_invoker(span: RhesisSpan, component_type: str | None) -> None:
        """
        Describe a Haystack 2.x ``ToolInvoker`` span by the tools it actually called.

        On 2.x an agent's tool calls arrive batched through one component span, whose input is the
        whole message history and whose output is the whole tool-message list. That is unreadable
        in a trace viewer and impossible to index by tool.

        Haystack 3.0 needs none of this: it opens an ``ai.tool.invoke`` span per call.
        """
        if component_type != "ToolInvoker":
            return

        data = span.get_data()
        tool_calls: list[dict[str, Any]] = []
        for message in data.get(mapping.COMPONENT_INPUT, {}).get("messages", []):
            if isinstance(message, ChatMessage) and message.tool_calls:
                tool_calls.extend(
                    {"id": call.id, "name": call.tool_name, "arguments": call.arguments}
                    for call in message.tool_calls
                )
        if not tool_calls:
            return

        otel_span = span.raw_span()
        tool_counts = Counter(call["name"] for call in tool_calls)
        formatted_names = [
            f"{name} (x{count})" if count > 1 else name
            for name, count in sorted(tool_counts.items())
        ]
        if hasattr(otel_span, "update_name"):
            component_name = data.get(mapping.COMPONENT_NAME, "ToolInvoker")
            otel_span.update_name(f"{component_name} - [{', '.join(formatted_names)}]")

        if not capture_content():
            return

        otel_span.set_attribute(
            AIAttributes.TOOL_INPUT_CONTENT, _stringify_content(tool_calls)[:MAX_CONTENT_LENGTH]
        )

        results: list[dict[str, Any]] = []
        for message in data.get(mapping.COMPONENT_OUTPUT, {}).get("tool_messages", []):
            if isinstance(message, ChatMessage) and message.tool_call_results:
                for result in message.tool_call_results:
                    origin = result.origin
                    results.append(
                        {
                            "id": origin.id if origin else None,
                            "name": origin.tool_name if origin else None,
                            "arguments": origin.arguments if origin else None,
                            "result": result.result,
                            "error": result.error,
                        }
                    )
        if results:
            otel_span.set_attribute(
                AIAttributes.TOOL_OUTPUT_CONTENT,
                _stringify_content(results)[:MAX_CONTENT_LENGTH],
            )

    @staticmethod
    def _apply_model_metadata(span: RhesisSpan, component_type: str | None) -> None:
        """Promote the model name and token usage a generator or embedder reported."""
        otel_span = span.raw_span()
        data = span.get_data()

        # In Haystack 3.0 the agent calls its chat generator directly, so the reply metadata
        # arrives on the agent-loop LLM span instead of a ChatGenerator component span.
        if span.operation_name == mapping.AGENT_STEP_LLM:
            llm_output = data.get(mapping.AGENT_STEP_LLM_OUTPUT)
            replies = llm_output.get("replies") if isinstance(llm_output, dict) else None
            if replies:
                _apply_chat_reply_metadata(otel_span, replies)

        elif component_type and component_type.endswith("ChatGenerator"):
            replies = data.get(mapping.COMPONENT_OUTPUT, {}).get("replies")
            if replies:
                _apply_chat_reply_metadata(otel_span, replies)

        elif component_type and component_type.endswith("Generator"):
            meta = data.get(mapping.COMPONENT_OUTPUT, {}).get("meta")
            if meta:
                model = meta[0].get("model")
                if model:
                    otel_span.set_attribute(AIAttributes.MODEL_NAME, model)
                _set_token_attributes(otel_span, meta[0].get("usage"))

        elif component_type and component_type.endswith("Embedder"):
            meta = data.get(mapping.COMPONENT_OUTPUT, {}).get("meta")
            if meta and isinstance(meta, dict):
                _set_token_attributes(otel_span, meta.get("usage") or meta.get("billed_units"))
                model = meta.get("model")
                if model and isinstance(model, str):
                    otel_span.set_attribute(AIAttributes.MODEL_NAME, model)


class RhesisTracer(Tracer):
    """Haystack tracer implementation that exports spans to Rhesis via OpenTelemetry."""

    def __init__(
        self,
        telemetry: RhesisTelemetry,
        name: str = "Haystack",
        span_handler: SpanHandler | None = None,
    ) -> None:
        """
        Initialize a RhesisTracer instance.

        :param telemetry: The Rhesis OpenTelemetry provider and tracer to open spans through.
        :param name: Trace name shown in the Rhesis UI.
        :param span_handler: Custom handler for span creation and enrichment.
        """
        if not proxy_tracer.is_content_tracing_enabled:
            logger.warning(
                "Traces will not include input/output content in Rhesis because Haystack content "
                "tracing is disabled. To enable, set HAYSTACK_CONTENT_TRACING_ENABLED=true before "
                "importing Haystack."
            )
        elif not content_capture_enabled():
            logger.info(
                "%s is set, so Haystack span content will not be recorded.",
                DISABLE_CONTENT_CAPTURE_ENV,
            )
        self._telemetry = telemetry
        self._name = name
        self.enforce_flush = enforce_flush_enabled()
        self._span_handler = span_handler or DefaultSpanHandler()
        self._span_handler.init_tracer(telemetry)

    @property
    def telemetry(self) -> RhesisTelemetry:
        """
        The Rhesis OTel provider and tracer backing this tracer.

        Public because a custom :class:`SpanHandler`, and the conversation turn spans in
        :class:`~rhesis.sdk.telemetry.integrations.haystack.conversation.RhesisTracing`, need to
        open spans on the same provider so they are flushed together with their children.
        """
        return self._telemetry

    @contextlib.contextmanager
    def trace(
        self,
        operation_name: str,
        tags: dict[str, Any] | None = None,
        parent_span: Span | None = None,
    ) -> Iterator[Span]:
        """Create and manage a tracing span as a context manager."""
        tags = tags or {}
        span_name = tags.get(mapping.COMPONENT_NAME, operation_name)
        component_type = tags.get(mapping.COMPONENT_TYPE)
        current = parent_span or self.current_span()
        is_root_span = not (parent_span or self.current_span())

        span_context = SpanContext(
            name=span_name,
            operation_name=operation_name,
            component_type=component_type,
            tags=tags,
            parent_span=current,
            trace_name=self._name,
            is_root=is_root_span,
        )

        span = self._span_handler.create_span(span_context)

        prev_stack = span_stack_var.get()
        new_stack = (prev_stack or []).copy()
        new_stack.append(span)
        token = span_stack_var.set(new_stack)

        trace_id_token = None
        # Give each run its own copy of the invocation context. A caller may set it from inside the
        # run with no teardown hook of its own, so without this restore point the value would still
        # be set when the *next* run's root span reads it -- attributing one user's turn to the
        # previous user's conversation.
        context_token = None
        if is_root_span:
            context_token = tracing_context_var.set(dict(tracing_context_var.get({})))
            try:
                raw_trace_id = span.raw_span().get_span_context().trace_id
                trace_id_token = trace_id_var.set(format(raw_trace_id, "032x"))
            except (AttributeError, TypeError):
                trace_id_token = trace_id_var.set("")

        span.set_tags(tags)

        try:
            yield span
        except Exception:
            exc_info = sys.exc_info()
            try:
                self._span_handler.handle(span, component_type)
                self._record_exception(span, exc_info)
                self._close_span(span, exc_info)
            except Exception as cleanup_error:  # noqa: BLE001
                logger.warning(
                    "Error during span cleanup for %s: %s", operation_name, cleanup_error
                )
            raise
        else:
            try:
                self._span_handler.handle(span, component_type)
                self._close_span(span, None)
            except Exception as cleanup_error:  # noqa: BLE001
                logger.warning(
                    "Error during span cleanup for %s: %s", operation_name, cleanup_error
                )
        finally:
            span_stack_var.reset(token)
            if trace_id_token is not None:
                trace_id_var.reset(trace_id_token)
            if context_token is not None:
                tracing_context_var.reset(context_token)
            # Root span only. Flushing every span turns one nine-span agent run into eleven
            # sequential single-span exports and leaves the BatchSpanProcessor nothing to batch;
            # gating on the root keeps the "everything is exported by the time the run returns"
            # guarantee for one export instead of eleven.
            if self.enforce_flush and is_root_span:
                self.flush()

    def _record_exception(self, span: RhesisSpan, exc_info: tuple[Any, Any, Any]) -> None:
        exc_type, exc_value, _ = exc_info
        if exc_type is None:
            return
        otel_span = span.raw_span()
        otel_span.set_status(Status(StatusCode.ERROR, str(exc_value)))
        otel_span.record_exception(exc_value)
        otel_span.set_attribute(AIAttributes.ERROR_TYPE, exc_type.__name__)

    def _close_span(self, span: RhesisSpan, exc_info: tuple[Any, Any, Any] | None) -> None:
        span.close(exc_info)

    def flush(self) -> None:
        """Flush all pending spans to Rhesis."""
        self._telemetry.flush()

    def current_span(self) -> Span | None:
        """Return the current active span."""
        stack = span_stack_var.get()
        return stack[-1] if stack else None

    def get_trace_url(self) -> str:
        """Return the frontend URL for the current trace, when available."""
        return build_trace_url(
            self._telemetry.frontend_url or "", self.get_trace_id(), self._telemetry.project_id
        )

    def get_trace_id(self) -> str:
        """Return the trace ID of the root span currently open in this context."""
        return trace_id_var.get()
