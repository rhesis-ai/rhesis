"""Translate OpenTelemetry GenAI semantic-convention spans into the Rhesis model.

Pure dict-in, dict-out functions with no OpenTelemetry SDK dependency, shared by
the SDK's framework integrations (which translate live ``ReadableSpan`` objects)
and the backend's OTLP ingest (which translates decoded protobuf spans).

Implements the conventions at :data:`GENAI_SEMCONV_VERSION`. They are still
"Development" status, so anything not recognised here passes through untouched:
translation only ever *adds* ``ai.*`` / ``rhesis.*`` keys next to the originals.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Collection, Mapping, Optional

from rhesis.telemetry.attributes import AIAttributes, AIEvents
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.schemas import AIOperationType

# Pinned spec: https://github.com/open-telemetry/semantic-conventions-genai
GENAI_SEMCONV_VERSION = "v0.1.0"
GENAI_SEMCONV_COMMIT = "d0e74ba6c48bcc4ded473b1828a8212f06b23753"

# ---------------------------------------------------------------------------
# Attribute names
# ---------------------------------------------------------------------------

GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_SYSTEM = "gen_ai.system"  # deprecated predecessor of provider.name
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"
GEN_AI_USAGE_CACHE_WRITE_INPUT_TOKENS = "gen_ai.usage.cache_write.input_tokens"
# The name before semantic-conventions-genai renamed it to cache_write.
GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS = "gen_ai.usage.cache_creation.input_tokens"
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_TYPE = "gen_ai.tool.type"
GEN_AI_TOOL_DESCRIPTION = "gen_ai.tool.description"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GEN_AI_TOOL_CALL_ARGS = "gen_ai.tool.call.arguments"
GEN_AI_TOOL_CALL_RESULT = "gen_ai.tool.call.result"
GEN_AI_TOOL_DEFINITIONS = "gen_ai.tool.definitions"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"
GEN_AI_AGENT_ID = "gen_ai.agent.id"
GEN_AI_AGENT_VERSION = "gen_ai.agent.version"
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
GEN_AI_TRANSFER_MODE = "gen_ai.transfer.mode"
GEN_AI_TRANSFER_TARGET_NAME = "gen_ai.transfer.target.name"

# Message content is recorded as span attributes holding the spec's JSON schemas:
#   gen_ai.input.messages / gen_ai.output.messages -> [{"role", "parts": [...]}, ...]
#   gen_ai.system_instructions -> [{"type": "text", "content": "..."}, ...]
GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
GEN_AI_SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions"

# Pointers to content held in external storage. Kept and shown, never fetched.
GEN_AI_REF_ATTRIBUTES = (
    "gen_ai.input.messages_ref",
    "gen_ai.output.messages_ref",
    "gen_ai.system_instructions_ref",
    "gen_ai.tool.definitions_ref",
)

# ---------------------------------------------------------------------------
# Operation values (gen_ai.operation.name)
# ---------------------------------------------------------------------------

OP_CHAT = "chat"
OP_TEXT_COMPLETION = "text_completion"
OP_GENERATE_CONTENT = "generate_content"
OP_REALTIME_INFERENCE = "realtime_inference"
OP_INVOKE_AGENT = "invoke_agent"
OP_INVOKE_WORKFLOW = "invoke_workflow"
OP_INVOKE_RUNNER = "invoke_runner"
OP_CREATE_AGENT = "create_agent"
OP_PLAN = "plan"
OP_EXECUTE_TOOL = "execute_tool"
OP_EMBEDDINGS = "embeddings"
OP_RETRIEVAL = "retrieval"

INFERENCE_OPERATIONS = frozenset(
    {OP_CHAT, OP_TEXT_COMPLETION, OP_GENERATE_CONTENT, OP_REALTIME_INFERENCE}
)

# create_memory_store -> create, search_memory -> search, ...
_MEMORY_OPERATION = re.compile(r"^(create|search|update|upsert|delete)_memory(_store)?$")

# Legacy per-message span events, still emitted by older instrumentations.
EVENT_SYSTEM_MESSAGE = "gen_ai.system.message"
EVENT_USER_MESSAGE = "gen_ai.user.message"
EVENT_ASSISTANT_MESSAGE = "gen_ai.assistant.message"
EVENT_TOOL_MESSAGE = "gen_ai.tool.message"
EVENT_CHOICE = "gen_ai.choice"

# Exception events (gen-ai-exceptions.md). Any name ending in ".exception" under
# gen_ai.* is treated the same way.
EXCEPTION_EVENT_SUFFIX = ".exception"

# Where the outermost invoke_* span's turn text goes; drives the trace list
# Input column, the conversation view and trace metrics.
CONVERSATION_INPUT = ConversationContext.SpanAttributes.CONVERSATION_INPUT
CONVERSATION_OUTPUT = ConversationContext.SpanAttributes.CONVERSATION_OUTPUT

# ---------------------------------------------------------------------------
# Operation -> span name / ai.operation.type
# ---------------------------------------------------------------------------

OPERATION_TO_AI_TYPE: Mapping[str, str] = {
    OP_CHAT: AIAttributes.OPERATION_LLM_INVOKE,
    OP_TEXT_COMPLETION: AIAttributes.OPERATION_LLM_INVOKE,
    OP_GENERATE_CONTENT: AIAttributes.OPERATION_LLM_INVOKE,
    OP_REALTIME_INFERENCE: AIAttributes.OPERATION_LLM_INVOKE,
    OP_INVOKE_AGENT: AIAttributes.OPERATION_AGENT_INVOKE,
    OP_CREATE_AGENT: AIAttributes.OPERATION_AGENT_CREATE,
    OP_PLAN: AIAttributes.OPERATION_AGENT_PLAN,
    OP_EXECUTE_TOOL: AIAttributes.OPERATION_TOOL_INVOKE,
    OP_EMBEDDINGS: AIAttributes.OPERATION_EMBEDDING_CREATE,
    OP_RETRIEVAL: AIAttributes.OPERATION_RETRIEVAL,
}

_OPERATION_TO_SPAN_NAME: Mapping[str, str] = {
    OP_CHAT: AIOperationType.LLM_INVOKE.value,
    OP_TEXT_COMPLETION: AIOperationType.LLM_INVOKE.value,
    OP_GENERATE_CONTENT: AIOperationType.LLM_INVOKE.value,
    OP_REALTIME_INFERENCE: AIOperationType.LLM_INVOKE.value,
    OP_CREATE_AGENT: AIOperationType.AGENT_CREATE.value,
    OP_PLAN: AIOperationType.AGENT_PLAN.value,
    OP_EXECUTE_TOOL: AIOperationType.TOOL_INVOKE.value,
    OP_EMBEDDINGS: AIOperationType.EMBEDDING_GENERATE.value,
    OP_RETRIEVAL: AIOperationType.RETRIEVAL_QUERY.value,
}

_MAX_SPAN_NAME_LENGTH = 255
_FUNCTION_PREFIX = "function."
_UNSAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9_.:/-]+")


def _is_operation(attributes: Mapping[str, Any], operations: Collection[str]) -> bool:
    # An attribute can arrive as an array value, which is not hashable.
    operation = attributes.get(GEN_AI_OPERATION_NAME)
    return isinstance(operation, str) and operation in operations


def is_invoke_operation(operation: Any) -> bool:
    """invoke_agent, invoke_workflow, invoke_runner and any other invoke_{entrypoint}."""
    return isinstance(operation, str) and operation.startswith("invoke_")


def is_transfer(attributes: Mapping[str, Any]) -> bool:
    """An execute_tool span that hands work to another agent (execute-tool.md, transfer)."""
    return (
        attributes.get(GEN_AI_TRANSFER_MODE) is not None
        or attributes.get(GEN_AI_TRANSFER_TARGET_NAME) is not None
    )


def operation_from_span_name(span_name: str) -> Optional[str]:
    """Recover the operation from a span named ``{operation} {target}``.

    Fallback for spans that omit ``gen_ai.operation.name``. Only accepts values
    this module knows, so an ordinary span named ``chat handler`` is not read as
    an inference call unless its first word is a known operation.
    """
    first = (span_name or "").split(" ", 1)[0]
    if first in _OPERATION_TO_SPAN_NAME or is_invoke_operation(first):
        return first
    if _MEMORY_OPERATION.match(first):
        return first
    return None


def function_span_name(span_name: str) -> str:
    """``function.<sanitised name>`` for spans with no GenAI meaning."""
    cleaned = _UNSAFE_NAME_CHARS.sub("_", (span_name or "").strip()).strip("_") or "span"
    return (_FUNCTION_PREFIX + cleaned)[:_MAX_SPAN_NAME_LENGTH]


def classify_span(span_name: str, attributes: Mapping[str, Any]) -> tuple[str, Optional[str]]:
    """Return ``(rhesis span_name, ai.operation.type or None)`` for a span.

    Classified by ``gen_ai.operation.name``, with the span name only as a
    fallback. Unknown operations and non-GenAI spans become ``function.<name>``
    so they are kept, not dropped.
    """
    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if not isinstance(operation, str) or not operation:
        operation = operation_from_span_name(span_name)
    if not operation:
        return function_span_name(span_name), None

    if operation == OP_EXECUTE_TOOL and is_transfer(attributes):
        return AIOperationType.AGENT_HANDOFF.value, AIAttributes.OPERATION_AGENT_HANDOFF
    if is_invoke_operation(operation):
        # "workflow" is a forbidden span domain; the original operation stays in
        # gen_ai.operation.name, which is always kept.
        return AIOperationType.AGENT_INVOKE.value, AIAttributes.OPERATION_AGENT_INVOKE
    memory = _MEMORY_OPERATION.match(operation)
    if memory:
        verb = memory.group(1)
        return f"ai.memory.{verb}", f"memory.{verb}"
    if operation in _OPERATION_TO_SPAN_NAME:
        return _OPERATION_TO_SPAN_NAME[operation], OPERATION_TO_AI_TYPE.get(operation)
    return function_span_name(span_name), None


# ---------------------------------------------------------------------------
# Attributes
# ---------------------------------------------------------------------------

# Direct renames. The first source present wins for a shared destination, so the
# requested model is preferred over the response model: it is what the caller
# asked for, and what cost and quota analytics group by.
_DIRECT_ATTR_MAP: tuple[tuple[str, str], ...] = (
    (GEN_AI_REQUEST_MODEL, AIAttributes.MODEL_NAME),
    (GEN_AI_RESPONSE_MODEL, AIAttributes.MODEL_NAME),
    (GEN_AI_PROVIDER_NAME, AIAttributes.MODEL_PROVIDER),
    (GEN_AI_SYSTEM, AIAttributes.MODEL_PROVIDER),
    (GEN_AI_REQUEST_TEMPERATURE, AIAttributes.LLM_TEMPERATURE),
    (GEN_AI_REQUEST_MAX_TOKENS, AIAttributes.LLM_MAX_TOKENS),
    (GEN_AI_TOOL_NAME, AIAttributes.TOOL_NAME),
    (GEN_AI_TOOL_TYPE, AIAttributes.TOOL_TYPE),
    (GEN_AI_TOOL_DESCRIPTION, AIAttributes.TOOL_DESCRIPTION),
    (GEN_AI_TOOL_CALL_ID, AIAttributes.TOOL_CALL_ID),
    (GEN_AI_AGENT_NAME, AIAttributes.AGENT_NAME),
    (GEN_AI_AGENT_ID, AIAttributes.AGENT_ID),
    (GEN_AI_AGENT_DESCRIPTION, AIAttributes.AGENT_DESCRIPTION),
    (GEN_AI_AGENT_VERSION, AIAttributes.AGENT_VERSION),
    (GEN_AI_CONVERSATION_ID, AIAttributes.SESSION_ID),
)


def _finish_reason(value: Any) -> Optional[str]:
    """One string, as the other integrations record it: the reasons joined with ", ".

    Instrumentations send an array, or that array as a JSON string.
    """
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return value
        value = decoded if isinstance(decoded, list) else value
    if isinstance(value, (list, tuple)):
        reasons = [str(v) for v in value if v is not None and v != ""]
        return ", ".join(reasons) if reasons else None
    return None if value is None else str(value)


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _translate_tokens(
    attributes: Mapping[str, Any], translated: dict[str, Any], input_includes_cache: bool
) -> None:
    """gen_ai.usage.* -> ai.llm.tokens.*.

    GenAI's input count includes cached tokens (registry note on
    ``gen_ai.usage.input_tokens``); Rhesis keeps them apart, with input + output +
    cache = total. So cache reads and writes are subtracted from input here,
    unless the instrumentation already reports input without them.
    """
    input_tokens = _as_int(attributes.get(GEN_AI_USAGE_INPUT_TOKENS))
    output_tokens = _as_int(attributes.get(GEN_AI_USAGE_OUTPUT_TOKENS))
    cache_read = _as_int(attributes.get(GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS))
    cache_write = _as_int(attributes.get(GEN_AI_USAGE_CACHE_WRITE_INPUT_TOKENS))
    if cache_write is None:
        cache_write = _as_int(attributes.get(GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS))

    if cache_read is not None:
        translated.setdefault(AIAttributes.LLM_TOKENS_CACHE_READ, cache_read)
    if cache_write is not None:
        translated.setdefault(AIAttributes.LLM_TOKENS_CACHE_WRITE, cache_write)
    if input_tokens is not None:
        uncached = input_tokens
        if input_includes_cache:
            uncached = max(input_tokens - (cache_read or 0) - (cache_write or 0), 0)
        translated.setdefault(AIAttributes.LLM_TOKENS_INPUT, uncached)
    if output_tokens is not None:
        translated.setdefault(AIAttributes.LLM_TOKENS_OUTPUT, output_tokens)
    if input_tokens is not None or output_tokens is not None:
        translated.setdefault(
            AIAttributes.LLM_TOKENS_TOTAL, (input_tokens or 0) + (output_tokens or 0)
        )


def translate_attributes(
    attributes: Mapping[str, Any], *, input_includes_cache: bool = True
) -> dict[str, Any]:
    """Return the span's attributes with Rhesis ``ai.*`` aliases added.

    Every original attribute is kept; aliases never overwrite a key already set.
    ``input_includes_cache=False`` is for instrumentations that, unlike the spec,
    report input tokens without the cached ones (Google ADK).
    """
    translated: dict[str, Any] = dict(attributes)

    for src, dst in _DIRECT_ATTR_MAP:
        if src in attributes and dst not in translated:
            translated[dst] = attributes[src]
    if (
        GEN_AI_RESPONSE_FINISH_REASONS in attributes
        and AIAttributes.LLM_FINISH_REASON not in attributes
    ):
        finish = _finish_reason(attributes[GEN_AI_RESPONSE_FINISH_REASONS])
        if finish is not None:
            translated[AIAttributes.LLM_FINISH_REASON] = finish

    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if isinstance(operation, str) and operation in OPERATION_TO_AI_TYPE:
        translated.setdefault(AIAttributes.OPERATION_TYPE, OPERATION_TO_AI_TYPE[operation])

    if attributes.get(GEN_AI_TRANSFER_TARGET_NAME) is not None:
        translated.setdefault(
            AIAttributes.AGENT_HANDOFF_TO, attributes[GEN_AI_TRANSFER_TARGET_NAME]
        )

    _translate_tokens(attributes, translated, input_includes_cache)
    return translated


# ---------------------------------------------------------------------------
# Legacy message events
# ---------------------------------------------------------------------------

# GenAI event name -> (Rhesis event name, role for prompt-style events).
_EVENT_NAME_MAP: Mapping[str, tuple[str, str | None]] = {
    EVENT_SYSTEM_MESSAGE: (AIEvents.PROMPT, "system"),
    EVENT_USER_MESSAGE: (AIEvents.PROMPT, "user"),
    EVENT_ASSISTANT_MESSAGE: (AIEvents.COMPLETION, None),
    EVENT_TOOL_MESSAGE: (AIEvents.TOOL_OUTPUT, None),
    EVENT_CHOICE: (AIEvents.COMPLETION, None),
}


def translate_event_name(event_name: str) -> str:
    """Map a GenAI span-event name to the Rhesis one, or return it unchanged."""
    mapping = _EVENT_NAME_MAP.get(event_name)
    return event_name if mapping is None else mapping[0]


def translate_event_attributes(event_name: str, attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Add Rhesis content keys to a legacy message event; originals are kept."""
    translated: dict[str, Any] = dict(attributes)
    mapping = _EVENT_NAME_MAP.get(event_name)
    if mapping is None:
        return translated

    rhesis_event, role = mapping
    body = attributes.get("body")
    content_value = body if isinstance(body, str) else attributes.get("content")

    if rhesis_event == AIEvents.PROMPT:
        if role is not None:
            translated.setdefault(AIAttributes.PROMPT_ROLE, role)
        if content_value is not None:
            translated.setdefault(AIAttributes.PROMPT_CONTENT, content_value)
    elif rhesis_event == AIEvents.COMPLETION:
        if content_value is not None:
            translated.setdefault(AIAttributes.COMPLETION_CONTENT, content_value)
    elif rhesis_event == AIEvents.TOOL_OUTPUT:
        if content_value is not None:
            translated.setdefault(AIAttributes.TOOL_OUTPUT_CONTENT, content_value)

    return translated


def is_exception_event(event_name: str) -> bool:
    """gen_ai.*.exception (gen-ai-exceptions.md) or the generic OTel ``exception`` event."""
    return event_name == "exception" or (
        event_name.startswith("gen_ai.") and event_name.endswith(EXCEPTION_EVENT_SUFFIX)
    )


def exception_message(attributes: Mapping[str, Any]) -> Optional[str]:
    """``type: message`` from an exception event's attributes, or whichever is set."""
    exc_type = attributes.get("exception.type")
    message = attributes.get("exception.message")
    if exc_type and message:
        return f"{exc_type}: {message}"
    if message or exc_type:
        return str(message or exc_type)
    return None


# ---------------------------------------------------------------------------
# Message content
# ---------------------------------------------------------------------------


def to_json_text(value: Any) -> str:
    """Render a payload as text: strings verbatim, anything else as JSON."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def coerce_message_list(value: Any) -> list[Any] | None:
    """Decode a ``gen_ai.*.messages`` value (JSON string or structured) into a list."""
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
    """Render a message's ``parts`` as one string; non-text parts as JSON."""
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return to_json_text(parts) if parts is not None else ""

    chunks: list[str] = []
    for part in parts:
        if isinstance(part, Mapping):
            if part.get("type") in ("text", "reasoning"):
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
    """Concatenate only ``text``/``reasoning`` parts; tool calls and blobs are skipped."""
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


def _messages_by_role(value: Any, role: str) -> list[str]:
    texts: list[str] = []
    for message in coerce_message_list(value) or ():
        if isinstance(message, Mapping) and message.get("role") == role:
            text = join_text_parts(message.get("parts")).strip()
            if text:
                texts.append(text)
    return texts


def extract_conversation_input(
    attributes: Mapping[str, Any],
    *,
    chat_operations: Collection[str] = (OP_CHAT,),
) -> str | None:
    """The first user message's text on an inference span, else ``None``."""
    if not _is_operation(attributes, chat_operations):
        return None
    texts = _messages_by_role(attributes.get(GEN_AI_INPUT_MESSAGES), "user")
    return texts[0] if texts else None


def extract_conversation_output(
    attributes: Mapping[str, Any],
    *,
    chat_operations: Collection[str] = (OP_CHAT,),
) -> str | None:
    """The assistant text on an inference span's output, else ``None``."""
    if not _is_operation(attributes, chat_operations):
        return None
    joined = "\n".join(_messages_by_role(attributes.get(GEN_AI_OUTPUT_MESSAGES), "assistant"))
    return joined.strip() or None


def agent_turn_input(attributes: Mapping[str, Any]) -> str | None:
    """The turn's input on an invoke_* span: its last user message.

    The input history of an agent invocation replays earlier turns, so the last
    user message is the one this turn answers.
    """
    texts = _messages_by_role(attributes.get(GEN_AI_INPUT_MESSAGES), "user")
    return texts[-1] if texts else None


def agent_turn_output(attributes: Mapping[str, Any]) -> str | None:
    """The turn's final answer on an invoke_* span: its last assistant text."""
    texts = _messages_by_role(attributes.get(GEN_AI_OUTPUT_MESSAGES), "assistant")
    return texts[-1] if texts else None


def _render_messages(value: Any) -> str:
    """All messages as ``role: content`` lines, for agent input/output events."""
    lines: list[str] = []
    for message in coerce_message_list(value) or ():
        if not isinstance(message, Mapping):
            continue
        content = join_message_parts(message.get("parts"))
        if content:
            role = message.get("role")
            lines.append(f"{role}: {content}" if isinstance(role, str) else content)
    return "\n".join(lines)


def synthesize_message_events(
    attributes: Mapping[str, Any],
    *,
    chat_operations: Collection[str] = (OP_CHAT,),
) -> list[tuple[str, dict[str, Any]]]:
    """``ai.prompt`` / ``ai.completion`` events from an inference span's messages.

    Only for the operations in ``chat_operations``, so agent and tool spans do
    not duplicate the model's content. Empty when content capture was off.
    """
    if not _is_operation(attributes, chat_operations):
        return []

    events: list[tuple[str, dict[str, Any]]] = []

    input_messages = coerce_message_list(attributes.get(GEN_AI_INPUT_MESSAGES)) or []
    system_instructions = coerce_message_list(attributes.get(GEN_AI_SYSTEM_INSTRUCTIONS))
    if system_instructions:
        content = join_message_parts(system_instructions)
        # Some instrumentations also repeat the instructions as a system message.
        repeated = any(
            isinstance(m, Mapping)
            and m.get("role") == "system"
            and join_message_parts(m.get("parts")) == content
            for m in input_messages
        )
        if content and not repeated:
            events.append(
                (
                    AIEvents.PROMPT,
                    {AIAttributes.PROMPT_ROLE: "system", AIAttributes.PROMPT_CONTENT: content},
                )
            )

    for message in input_messages:
        if not isinstance(message, Mapping):
            continue
        content = join_message_parts(message.get("parts"))
        if not content:
            continue
        role = message.get("role")
        events.append(
            (
                AIEvents.PROMPT,
                {
                    AIAttributes.PROMPT_ROLE: role if isinstance(role, str) else "user",
                    AIAttributes.PROMPT_CONTENT: content,
                },
            )
        )

    output_messages = coerce_message_list(attributes.get(GEN_AI_OUTPUT_MESSAGES))
    if output_messages:
        chunks = [
            join_message_parts(m.get("parts")) for m in output_messages if isinstance(m, Mapping)
        ]
        joined = "\n".join(c for c in chunks if c).strip()
        if joined:
            events.append((AIEvents.COMPLETION, {AIAttributes.COMPLETION_CONTENT: joined}))

    return events


def synthesize_agent_io_events(attributes: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """``ai.agent.input`` / ``ai.agent.output`` events from an invoke_* span's messages."""
    if not is_invoke_operation(attributes.get(GEN_AI_OPERATION_NAME)):
        return []
    events: list[tuple[str, dict[str, Any]]] = []
    rendered_input = _render_messages(attributes.get(GEN_AI_INPUT_MESSAGES))
    if rendered_input:
        events.append((AIEvents.AGENT_INPUT, {AIAttributes.AGENT_INPUT_CONTENT: rendered_input}))
    rendered_output = _render_messages(attributes.get(GEN_AI_OUTPUT_MESSAGES))
    if rendered_output:
        events.append((AIEvents.AGENT_OUTPUT, {AIAttributes.AGENT_OUTPUT_CONTENT: rendered_output}))
    return events


def synthesize_tool_io_events(
    attributes: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """``ai.tool.input`` / ``ai.tool.output`` events from tool call arguments and result."""
    events: list[tuple[str, dict[str, Any]]] = []
    args = attributes.get(GEN_AI_TOOL_CALL_ARGS)
    if args is not None:
        events.append((AIEvents.TOOL_INPUT, {AIAttributes.TOOL_INPUT_CONTENT: to_json_text(args)}))
    result = attributes.get(GEN_AI_TOOL_CALL_RESULT)
    if result is not None:
        events.append(
            (AIEvents.TOOL_OUTPUT, {AIAttributes.TOOL_OUTPUT_CONTENT: to_json_text(result)})
        )
    return events
