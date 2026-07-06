"""Shared helpers for integrations built on native GenAI OTel instrumentation.

Frameworks like Microsoft Agent Framework and Pydantic AI emit OpenTelemetry
spans natively following the GenAI semantic conventions (``gen_ai.*``
attributes, ``chat`` / ``invoke_agent`` / ``execute_tool`` operations). The
Rhesis backend expects the ``ai.*`` / ``function.*`` schema instead. This
module owns the framework-neutral pieces of that bridge so each integration
does not grow its own copy (see the coordination note on issue #2070):

- the ``gen_ai.*`` attribute-name constants and operation values,
- pure attribute / span-event translation tables,
- synthesis of ``ai.prompt`` / ``ai.completion`` / ``ai.tool.*`` span events
  from the attribute-based GenAI message convention,
- :class:`TranslatedSpan`, a read-only ``ReadableSpan`` view that swaps the
  name / attributes / events while delegating everything else,
- helpers to swap the exporter under an existing span processor, and
- the shared content-capture opt-out env var.

Framework-specific logic (span-name maps, workflow spans, handoff heuristics)
stays in each integration's own ``mapping.py`` / ``translator.py``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable, Mapping, Optional, Sequence

from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter

from rhesis.sdk.telemetry.attributes import AIAttributes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GenAI semantic-convention attribute names and operation values
# ---------------------------------------------------------------------------

GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_TYPE = "gen_ai.tool.type"
GEN_AI_TOOL_DESCRIPTION = "gen_ai.tool.description"
GEN_AI_TOOL_CALL_ARGS = "gen_ai.tool.call.arguments"
GEN_AI_TOOL_CALL_RESULT = "gen_ai.tool.call.result"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"
GEN_AI_AGENT_ID = "gen_ai.agent.id"
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"

# The current OTel GenAI semantic conventions record message content as span
# *attributes* carrying JSON arrays, rather than as the legacy per-message
# span *events* (``gen_ai.user.message`` etc.). The shape is::
#
#     gen_ai.input.messages    -> [{"role": "user", "parts": [{"type": "text",
#                                   "content": "..."}, ...]}, ...]
#     gen_ai.output.messages   -> same shape (last item may carry finish_reason)
#     gen_ai.system_instructions -> [{"type": "text", "content": "..."}, ...]
#
# We translate these into synthetic ``ai.prompt`` / ``ai.completion`` events so
# the Rhesis trace UI (which reads those events) renders the messages.
GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
GEN_AI_SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions"

# GenAI operation values (gen_ai.operation.name)
OP_CHAT = "chat"
OP_INVOKE_AGENT = "invoke_agent"
OP_CREATE_AGENT = "create_agent"
OP_EXECUTE_TOOL = "execute_tool"
OP_EMBEDDINGS = "embeddings"

# Legacy per-message span events
EVENT_SYSTEM_MESSAGE = "gen_ai.system.message"
EVENT_USER_MESSAGE = "gen_ai.user.message"
EVENT_ASSISTANT_MESSAGE = "gen_ai.assistant.message"
EVENT_TOOL_MESSAGE = "gen_ai.tool.message"
EVENT_CHOICE = "gen_ai.choice"

# Direct gen_ai.* -> ai.* attribute renames. Token attributes use a small
# helper because Rhesis stores total tokens explicitly while GenAI computes it.
#
# "First key wins" rule for collisions: ``GEN_AI_REQUEST_MODEL`` and
# ``GEN_AI_RESPONSE_MODEL`` both target ``AIAttributes.MODEL_NAME``. Insertion
# order is the iteration order of a dict in Python 3.7+ and
# :func:`translate_attributes` only writes a destination key once
# (``setdefault``), so the request model is preferred whenever both attributes
# are present. This is intentional: the request model is what the caller asked
# for, and is more useful for downstream cost / quota analytics. The response
# model still wins on its own when the request model is missing (e.g. some
# providers omit it).
_DIRECT_ATTR_MAP: Mapping[str, str] = {
    GEN_AI_REQUEST_MODEL: AIAttributes.MODEL_NAME,
    GEN_AI_RESPONSE_MODEL: AIAttributes.MODEL_NAME,
    GEN_AI_PROVIDER_NAME: AIAttributes.MODEL_PROVIDER,
    GEN_AI_SYSTEM: AIAttributes.MODEL_PROVIDER,
    GEN_AI_REQUEST_TEMPERATURE: AIAttributes.LLM_TEMPERATURE,
    GEN_AI_REQUEST_MAX_TOKENS: AIAttributes.LLM_MAX_TOKENS,
    GEN_AI_RESPONSE_FINISH_REASONS: AIAttributes.LLM_FINISH_REASON,
    GEN_AI_TOOL_NAME: AIAttributes.TOOL_NAME,
    GEN_AI_TOOL_TYPE: AIAttributes.TOOL_TYPE,
    GEN_AI_AGENT_NAME: AIAttributes.AGENT_NAME,
    GEN_AI_CONVERSATION_ID: AIAttributes.SESSION_ID,
}

# Operation -> Rhesis ai.operation.type value
OPERATION_TO_AI_TYPE: Mapping[str, str] = {
    OP_CHAT: AIAttributes.OPERATION_LLM_INVOKE,
    OP_INVOKE_AGENT: AIAttributes.OPERATION_AGENT_INVOKE,
    OP_CREATE_AGENT: AIAttributes.OPERATION_AGENT_INVOKE,
    OP_EXECUTE_TOOL: AIAttributes.OPERATION_TOOL_INVOKE,
    OP_EMBEDDINGS: AIAttributes.OPERATION_EMBEDDING_CREATE,
}


def translate_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Build the translated attribute set for a GenAI-convention span.

    The original ``gen_ai.*`` attributes are preserved (passthrough), and
    Rhesis ``ai.*`` aliases are added on top so both conventions coexist.

    Args:
        attributes: The span's raw attribute map.

    Returns:
        A new dict with both the original and translated attributes.
    """
    translated: dict[str, Any] = dict(attributes)

    for src, dst in _DIRECT_ATTR_MAP.items():
        if src in attributes and dst not in translated:
            translated[dst] = attributes[src]

    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if isinstance(operation, str) and operation in OPERATION_TO_AI_TYPE:
        translated.setdefault(AIAttributes.OPERATION_TYPE, OPERATION_TO_AI_TYPE[operation])

    input_tokens = attributes.get(GEN_AI_USAGE_INPUT_TOKENS)
    output_tokens = attributes.get(GEN_AI_USAGE_OUTPUT_TOKENS)

    if input_tokens is not None:
        translated.setdefault(AIAttributes.LLM_TOKENS_INPUT, input_tokens)
    if output_tokens is not None:
        translated.setdefault(AIAttributes.LLM_TOKENS_OUTPUT, output_tokens)
    if input_tokens is not None or output_tokens is not None:
        total = (input_tokens or 0) + (output_tokens or 0)
        translated.setdefault(AIAttributes.LLM_TOKENS_TOTAL, total)

    return translated


# Mapping: GenAI event name -> (Rhesis event name, role for prompt-style events).
# ``None`` for the role means "do not override role attribute".
_EVENT_NAME_MAP: Mapping[str, tuple[str, str | None]] = {
    EVENT_SYSTEM_MESSAGE: ("ai.prompt", "system"),
    EVENT_USER_MESSAGE: ("ai.prompt", "user"),
    EVENT_ASSISTANT_MESSAGE: ("ai.completion", None),
    EVENT_TOOL_MESSAGE: ("ai.tool.output", None),
    EVENT_CHOICE: ("ai.completion", None),
}


def translate_event_name(event_name: str) -> str:
    """Map a GenAI span-event name to the Rhesis equivalent.

    Returns the original name when no mapping exists.
    """
    mapping = _EVENT_NAME_MAP.get(event_name)
    if mapping is None:
        return event_name
    return mapping[0]


def translate_event_attributes(event_name: str, attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Translate the attributes of a single span event into Rhesis form.

    For prompt-style events we promote the role into ``ai.prompt.role`` and
    mirror the body content into ``ai.prompt.content`` /
    ``ai.completion.content`` / ``ai.tool.output``. Original attributes are
    passed through.
    """
    translated: dict[str, Any] = dict(attributes)
    mapping = _EVENT_NAME_MAP.get(event_name)
    if mapping is None:
        return translated

    rhesis_event, role = mapping

    body = attributes.get("body")
    content_value: Any | None = None
    if isinstance(body, str):
        content_value = body
    else:
        content_value = attributes.get("content")

    if rhesis_event == "ai.prompt":
        if role is not None:
            translated.setdefault(AIAttributes.PROMPT_ROLE, role)
        if content_value is not None:
            translated.setdefault(AIAttributes.PROMPT_CONTENT, content_value)
    elif rhesis_event == "ai.completion":
        if content_value is not None:
            translated.setdefault(AIAttributes.COMPLETION_CONTENT, content_value)
    elif rhesis_event == "ai.tool.output":
        if content_value is not None:
            translated.setdefault(AIAttributes.TOOL_OUTPUT_CONTENT, content_value)

    return translated


def to_json_text(value: Any) -> str:
    """Render a tool I/O payload as JSON-friendly text.

    GenAI instrumentations store ``gen_ai.tool.call.{arguments,result}`` as
    one of:

    - a JSON-encoded string (the OpenAI-compat path serialises tool arguments
      this way before handing them to the model),
    - a primitive (``str`` / ``int`` / ``float`` / ``bool`` / ``None``),
    - or an already-decoded ``dict`` / ``list``.

    For strings we pass through verbatim so we don't double-encode existing
    JSON. For everything else we ``json.dumps`` with ``default=str`` as a
    safety net for non-serialisable objects (datetimes, Pydantic models, ...).
    If ``dumps`` itself raises (e.g. circular references) we fall back to the
    Python ``str()`` repr so we never drop the event entirely.
    """
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def coerce_message_list(value: Any) -> list[Any] | None:
    """Decode a ``gen_ai.*.messages`` attribute into a list, defensively.

    Instrumentations store the value as a JSON-encoded string, but tolerate an
    already-decoded ``list`` too. Returns ``None`` when the value is missing,
    malformed, or not a list so callers can skip it without raising.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def join_message_parts(parts: Any) -> str:
    """Render a message's ``parts`` list into a single display string.

    Text and reasoning parts are concatenated verbatim; non-text parts (tool
    calls, blobs, ...) are JSON-encoded so they remain visible rather than
    dropped. Falls back to an empty string for unexpected shapes.
    """
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return to_json_text(parts) if parts is not None else ""

    chunks: list[str] = []
    for part in parts:
        if isinstance(part, Mapping):
            part_type = part.get("type")
            if part_type in ("text", "reasoning"):
                content = part.get("content")
                if content is not None:
                    chunks.append(content if isinstance(content, str) else to_json_text(content))
                continue
            chunks.append(to_json_text(part))
        elif isinstance(part, str):
            chunks.append(part)
        elif part is not None:
            chunks.append(to_json_text(part))
    return "".join(chunks)


def join_text_parts(parts: Any) -> str:
    """Concatenate only the human-readable ``text``/``reasoning`` parts.

    Unlike :func:`join_message_parts`, non-text parts (tool calls, blobs, ...)
    are skipped rather than JSON-encoded. Used for conversation input/output
    capture, where we want the user's query and the assistant's prose answer,
    not the JSON of a tool call.
    """
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, Mapping):
            if part.get("type") in ("text", "reasoning"):
                content = part.get("content")
                if isinstance(content, str):
                    chunks.append(content)
        elif isinstance(part, str):
            chunks.append(part)
    return "".join(chunks)


def extract_conversation_input(attributes: Mapping[str, Any]) -> str | None:
    """Return the original user query text from a chat span's input messages.

    Reads ``gen_ai.input.messages`` and returns the text of the first
    ``role == "user"`` message. Returns ``None`` for non-chat spans,
    missing/empty content, or when capture is disabled.
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_CHAT:
        return None
    messages = coerce_message_list(attributes.get(GEN_AI_INPUT_MESSAGES))
    if not messages:
        return None
    for message in messages:
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        content = join_text_parts(message.get("parts")).strip()
        if content:
            return content
    return None


def extract_conversation_output(attributes: Mapping[str, Any]) -> str | None:
    """Return the assistant response text from a chat span's output messages.

    Reads ``gen_ai.output.messages`` and joins the text parts of every
    ``role == "assistant"`` message. Tool-call-only turns yield an empty
    string and are skipped. Returns ``None`` for non-chat spans or when there
    is no assistant text output.
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_CHAT:
        return None
    messages = coerce_message_list(attributes.get(GEN_AI_OUTPUT_MESSAGES))
    if not messages:
        return None
    chunks: list[str] = []
    for message in messages:
        if not isinstance(message, Mapping) or message.get("role") != "assistant":
            continue
        content = join_text_parts(message.get("parts")).strip()
        if content:
            chunks.append(content)
    joined = "\n".join(chunks).strip()
    return joined or None


def synthesize_message_events(
    attributes: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Build ``ai.prompt`` / ``ai.completion`` events from GenAI message attrs.

    Translates the attribute-based GenAI message convention
    (``gen_ai.system_instructions`` / ``gen_ai.input.messages`` /
    ``gen_ai.output.messages``) into the span events the Rhesis trace UI reads.
    Only applies to chat spans (``gen_ai.operation.name == "chat"``) so we do
    not duplicate LLM content onto agent/tool spans.

    Returns an empty list when this is not a chat span or no message attributes
    are present (e.g. content capture disabled).
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_CHAT:
        return []

    events: list[tuple[str, dict[str, Any]]] = []

    system_instructions = coerce_message_list(attributes.get(GEN_AI_SYSTEM_INSTRUCTIONS))
    if system_instructions:
        content = join_message_parts(system_instructions)
        if content:
            events.append(
                (
                    "ai.prompt",
                    {
                        AIAttributes.PROMPT_ROLE: "system",
                        AIAttributes.PROMPT_CONTENT: content,
                    },
                )
            )

    input_messages = coerce_message_list(attributes.get(GEN_AI_INPUT_MESSAGES))
    for message in input_messages or ():
        if not isinstance(message, Mapping):
            continue
        content = join_message_parts(message.get("parts"))
        if not content:
            continue
        role = message.get("role")
        events.append(
            (
                "ai.prompt",
                {
                    AIAttributes.PROMPT_ROLE: role if isinstance(role, str) else "user",
                    AIAttributes.PROMPT_CONTENT: content,
                },
            )
        )

    output_messages = coerce_message_list(attributes.get(GEN_AI_OUTPUT_MESSAGES))
    if output_messages:
        completion_chunks: list[str] = []
        for message in output_messages:
            if not isinstance(message, Mapping):
                continue
            content = join_message_parts(message.get("parts"))
            if content:
                completion_chunks.append(content)
        joined = "\n".join(completion_chunks).strip()
        if joined:
            events.append(("ai.completion", {AIAttributes.COMPLETION_CONTENT: joined}))

    return events


def synthesize_tool_io_events(
    attributes: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Build synthetic ``ai.tool.input``/``ai.tool.output`` events from GenAI attrs.

    GenAI instrumentations store tool arguments and results as span
    *attributes* rather than as span events; the Rhesis backend renders them
    as events. This helper produces the events the translator should attach in
    addition to those already emitted by the framework.
    """
    events: list[tuple[str, dict[str, Any]]] = []
    args = attributes.get(GEN_AI_TOOL_CALL_ARGS)
    if args is not None:
        events.append(("ai.tool.input", {AIAttributes.TOOL_INPUT_CONTENT: to_json_text(args)}))
    result = attributes.get(GEN_AI_TOOL_CALL_RESULT)
    if result is not None:
        events.append(("ai.tool.output", {AIAttributes.TOOL_OUTPUT_CONTENT: to_json_text(result)}))
    return events


# ---------------------------------------------------------------------------
# TranslatedSpan: read-only ReadableSpan view with swapped name/attrs/events
# ---------------------------------------------------------------------------


class TranslatedSpan(ReadableSpan):
    """Read-only view that swaps the original span's name/attributes/events.

    OTEL ``ReadableSpan`` exposes its data via properties. By overriding only
    the three we care about we get a span that quacks like the original (kind,
    parent, status, timestamps, resource, instrumentation_scope, ...) but that
    appears in the Rhesis ``ai.*`` namespace to downstream consumers.
    """

    def __init__(
        self,
        original: ReadableSpan,
        new_name: str,
        new_attributes: Mapping[str, Any],
        new_events: Sequence[Event],
    ) -> None:
        # Skip ReadableSpan.__init__ on purpose: the parent stores fields in
        # private slots and forces us to copy them all over. Instead, we keep
        # the underlying span and forward unknown attribute access via
        # ``__getattr__`` below.
        self._original = original
        self._new_name = new_name
        self._new_attributes = dict(new_attributes)
        self._new_events = tuple(new_events)

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._new_name

    @property
    def attributes(self):  # type: ignore[override]
        return self._new_attributes

    @property
    def events(self):  # type: ignore[override]
        return self._new_events

    def __getattr__(self, item: str) -> Any:
        # __getattr__ is only consulted when normal lookup fails, so it never
        # masks the explicit overrides above.
        return getattr(self._original, item)

    def to_json(self, indent: int = 4) -> str:  # type: ignore[override]
        return self._original.to_json(indent=indent)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"TranslatedSpan(name={self._new_name!r}, original={self._original!r})"


def translate_events(
    original_events: Iterable[Event],
    span_attributes: Mapping[str, Any],
) -> list[Event]:
    """Build the new event list, including synthesized message/tool I/O events."""
    new_events: list[Event] = []
    for event in original_events:
        new_name = translate_event_name(event.name)
        new_attrs = translate_event_attributes(event.name, event.attributes or {})
        new_events.append(Event(name=new_name, attributes=new_attrs, timestamp=event.timestamp))

    for synth_name, synth_attrs in synthesize_message_events(span_attributes):
        new_events.append(Event(name=synth_name, attributes=synth_attrs))

    for synth_name, synth_attrs in synthesize_tool_io_events(span_attributes):
        new_events.append(Event(name=synth_name, attributes=synth_attrs))

    return new_events


# ---------------------------------------------------------------------------
# Exporter swapping on existing span processors
# ---------------------------------------------------------------------------


def get_processor_exporter(processor: SpanProcessor) -> Optional[SpanExporter]:
    """Read the underlying exporter on a span processor across OTEL SDK versions.

    Mirrors :func:`set_processor_exporter` so the read and write paths use the
    same detection. Today both layouts resolve via the public ``span_exporter``
    attribute (newer ``BatchSpanProcessor`` exposes it as a property that
    delegates to ``self._batch_processor._exporter``), but probing the inner
    slot first is defense-in-depth: if a future OTEL release drops the
    convenience property, the reader still finds the exporter the same way the
    writer would set it.
    """
    inner = getattr(processor, "_batch_processor", None)
    if inner is not None:
        exp = getattr(inner, "_exporter", None)
        if exp is not None:
            return exp
    return getattr(processor, "span_exporter", None)


def set_processor_exporter(processor: SpanProcessor, exporter: SpanExporter) -> None:
    """Set the underlying exporter on a span processor across OTEL SDK versions.

    Works for both :class:`BatchSpanProcessor` and :class:`SimpleSpanProcessor`:

    - Newer ``BatchSpanProcessor`` exposes the exporter as a read-only property
      that delegates to ``self._batch_processor._exporter``; we set the inner
      slot directly.
    - Older ``BatchSpanProcessor`` and ``SimpleSpanProcessor`` keep
      ``span_exporter`` as a plain settable attribute.

    We try the inner attribute first (newer Batch layout), then fall back to
    direct assignment (Simple / older Batch).
    """
    inner = getattr(processor, "_batch_processor", None)
    if inner is not None and hasattr(inner, "_exporter"):
        inner._exporter = exporter  # noqa: SLF001
        return
    # Older OTEL Batch SDK or SimpleSpanProcessor: span_exporter is a plain
    # attribute we can set directly.
    setattr(processor, "span_exporter", exporter)


# ---------------------------------------------------------------------------
# Content-capture opt-out (shared env var across integrations)
# ---------------------------------------------------------------------------

# Opt-out env var for message/tool content capture. When truthy, integrations
# disable their framework's sensitive-data capture so prompts, completions,
# and tool arguments/results are NOT captured into spans.
DISABLE_CONTENT_CAPTURE_ENV = "RHESIS_DISABLE_CONTENT_CAPTURE"

# Truthy string values for opt-in/out env vars.
TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def content_capture_enabled() -> bool:
    """Return whether frameworks should capture message/tool content into spans.

    Defaults to ``True`` because the whole point of the Rhesis integration is
    to ship prompts/completions/tool I/O to the backend so they render in the
    trace UI. Privacy-sensitive deployments can opt out by setting
    ``RHESIS_DISABLE_CONTENT_CAPTURE`` to a truthy value (``1``/``true``/
    ``yes``/``on``).
    """
    raw = os.getenv(DISABLE_CONTENT_CAPTURE_ENV)
    if raw is None:
        return True
    return raw.strip().lower() not in TRUTHY_ENV_VALUES
