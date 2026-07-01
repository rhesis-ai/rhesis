"""Pure-data translation tables for Microsoft Agent Framework spans.

Microsoft Agent Framework (MAF) emits spans following the OpenTelemetry GenAI
semantic conventions, with span names like ``"chat gpt-4"`` /
``"invoke_agent assistant"`` / ``"execute_tool calculator"`` and attributes in
the ``gen_ai.*`` namespace.

The Rhesis backend, by contrast, expects span names from the ``ai.*`` /
``function.*`` namespaces (see :mod:`rhesis.sdk.telemetry.attributes`). This
module owns the small set of translation tables needed to bridge the two.

The functions here are deliberately pure: no OTEL imports, no side effects.
That makes them trivial to unit test.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import AIOperationType

INSTRUMENTATION_SCOPE_PREFIX = "agent_framework"

# MAF's top-level workflow execution span name. It is the structural root of a
# workflow run (every executor/agent/chat/tool span nests under it). The
# translator treats it as the Rhesis conversation turn root when it is also the
# trace root (i.e. the workflow was run directly, not inside an enclosing
# Rhesis @endpoint/@observe span).
WORKFLOW_RUN_SPAN_NAME = "workflow.run"

# MAF's HandoffBuilder workflow implements agent-to-agent handoffs as
# auto-generated tool calls named ``handoff_to_<target_agent>``. These are
# scheduling primitives, not real domain tools — we recognise them so the
# translator can re-emit them as ``ai.agent.handoff`` spans that the Rhesis
# Graph View knows how to connect.
HANDOFF_TOOL_PREFIX = "handoff_to_"

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

# Newer MAF (and the current OTel GenAI semantic conventions) record message
# content as span *attributes* carrying JSON arrays, rather than as the legacy
# per-message span *events* (``gen_ai.user.message`` etc.). The shape is::
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

# MAF operation values (gen_ai.operation.name)
OP_CHAT = "chat"
OP_INVOKE_AGENT = "invoke_agent"
OP_CREATE_AGENT = "create_agent"
OP_EXECUTE_TOOL = "execute_tool"
OP_EMBEDDINGS = "embeddings"

# MAF span events
EVENT_SYSTEM_MESSAGE = "gen_ai.system.message"
EVENT_USER_MESSAGE = "gen_ai.user.message"
EVENT_ASSISTANT_MESSAGE = "gen_ai.assistant.message"
EVENT_TOOL_MESSAGE = "gen_ai.tool.message"
EVENT_CHOICE = "gen_ai.choice"

# Operation -> Rhesis span name. The validator in
# :mod:`rhesis.sdk.telemetry.attributes` accepts ``ai.<domain>(.<action>)?`` and
# anything starting with ``function.``, so we are careful to land here.
_OPERATION_TO_SPAN_NAME: Mapping[str, str] = {
    OP_CHAT: AIOperationType.LLM_INVOKE,
    OP_INVOKE_AGENT: "ai.agent.invoke",
    OP_CREATE_AGENT: "ai.agent.invoke",
    OP_EXECUTE_TOOL: AIOperationType.TOOL_INVOKE,
    OP_EMBEDDINGS: AIOperationType.EMBEDDING_GENERATE,
}

# Operation -> Rhesis ai.operation.type value
_OPERATION_TO_AI_TYPE: Mapping[str, str] = {
    OP_CHAT: AIAttributes.OPERATION_LLM_INVOKE,
    OP_INVOKE_AGENT: AIAttributes.OPERATION_AGENT_INVOKE,
    OP_CREATE_AGENT: AIAttributes.OPERATION_AGENT_INVOKE,
    OP_EXECUTE_TOOL: AIAttributes.OPERATION_TOOL_INVOKE,
    OP_EMBEDDINGS: AIAttributes.OPERATION_EMBEDDING_CREATE,
}

# Workflow span name prefixes (MAF emits e.g. "workflow.run", "executor.process",
# "edge_group.process", "message.send", "workflow.build"). These don't fit the
# ``ai.*`` namespace, so we land them under ``function.workflow.*`` which the
# Rhesis validator accepts unconditionally.
_WORKFLOW_PREFIX_MAP: Mapping[str, str] = {
    "workflow.": "function.workflow.",
    "executor.": "function.workflow.executor.",
    "edge_group.": "function.workflow.edge_group.",
    "message.send": "function.workflow.message.send",
    "build.": "function.workflow.build.",
}

# Direct gen_ai.* -> ai.* attribute renames. Token attributes use a small
# helper because Rhesis stores total tokens explicitly while MAF computes it.
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


def is_maf_scope(scope_name: str | None) -> bool:
    """Return True if the OTEL instrumentation scope belongs to MAF."""
    if not scope_name:
        return False
    return scope_name.startswith(INSTRUMENTATION_SCOPE_PREFIX)


def translate_span_name(original_name: str, attributes: Mapping[str, Any]) -> str:
    """Translate a MAF span name to the Rhesis ``ai.*`` / ``function.*`` schema.

    The translation prefers the explicit ``gen_ai.operation.name`` attribute
    (precise) and falls back to scanning the original span name (fuzzy). For
    workflow spans we map by prefix.

    If neither path matches, we sanitize ``original_name`` into the
    ``function.maf.*`` namespace so it always satisfies
    :func:`rhesis.sdk.telemetry.attributes.validate_span_name`. This protects
    the integration against MAF adding new operations under us.

    Args:
        original_name: The span name MAF assigned (e.g. ``"chat gpt-4"``).
        attributes: The span's attribute map.

    Returns:
        A Rhesis-shaped span name (always either ``ai.*`` or ``function.*``).
    """
    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if isinstance(operation, str) and operation in _OPERATION_TO_SPAN_NAME:
        return _OPERATION_TO_SPAN_NAME[operation]

    # Fuzzy fallback: the name starts with a known operation token
    if original_name:
        leading = original_name.split(" ", 1)[0]
        if leading in _OPERATION_TO_SPAN_NAME:
            return _OPERATION_TO_SPAN_NAME[leading]

        for prefix, replacement in _WORKFLOW_PREFIX_MAP.items():
            if original_name == prefix.rstrip("."):
                return replacement.rstrip(".")
            if original_name.startswith(prefix):
                tail = original_name[len(prefix) :]
                if not tail:
                    return replacement.rstrip(".")
                # Sanitize tail to be a valid function.* segment (lowercase, no
                # whitespace) - the Rhesis validator just requires the leading
                # ``function.`` token, so this is mostly cosmetic.
                tail = tail.replace(" ", "_").lower()
                return f"{replacement}{tail}".rstrip(".")

    return fallback_function_maf_name(original_name)


def fallback_function_maf_name(original_name: str) -> str:
    """Last-resort name sanitizer that always satisfies ``validate_span_name``.

    The Rhesis backend rejects anything that is not ``ai.<domain>(.<action>)?``
    or ``function.<...>``. Names like ``"chat gpt-4o"`` (with a space) or a
    brand-new MAF operation we have not mapped would otherwise fail validation
    and be dropped with HTTP 422. Funneling unknowns into ``function.maf.*``
    keeps them visible in the trace tree without claiming a specific ``ai.*``
    semantic.

    Also used by :class:`MAFTranslatingExporter` as the fallback span name when
    full translation raises — better to land an unmapped-but-valid name than
    forward the raw ``"chat gpt-4"`` name (which the backend rejects with
    HTTP 422 and silently drops).
    """
    if not original_name:
        return "function.maf.unknown"
    sanitized = original_name.replace(" ", "_").replace(".", "_").lower()
    return f"function.maf.{sanitized}"


def translate_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Build the translated attribute set for a MAF span.

    The original ``gen_ai.*`` attributes are preserved (passthrough), and
    Rhesis ``ai.*`` aliases are added on top so both conventions coexist.

    Args:
        attributes: The MAF span's raw attribute map.

    Returns:
        A new dict with both the original and translated attributes.
    """
    translated: dict[str, Any] = dict(attributes)

    for src, dst in _DIRECT_ATTR_MAP.items():
        if src in attributes and dst not in translated:
            translated[dst] = attributes[src]

    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if isinstance(operation, str) and operation in _OPERATION_TO_AI_TYPE:
        translated.setdefault(AIAttributes.OPERATION_TYPE, _OPERATION_TO_AI_TYPE[operation])

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


# Mapping: MAF event name -> (Rhesis event name, role for prompt-style events).
# ``None`` for the role means "do not override role attribute".
_EVENT_NAME_MAP: Mapping[str, tuple[str, str | None]] = {
    EVENT_SYSTEM_MESSAGE: ("ai.prompt", "system"),
    EVENT_USER_MESSAGE: ("ai.prompt", "user"),
    EVENT_ASSISTANT_MESSAGE: ("ai.completion", None),
    EVENT_TOOL_MESSAGE: ("ai.tool.output", None),
    EVENT_CHOICE: ("ai.completion", None),
}


def translate_event_name(event_name: str) -> str:
    """Map a MAF span-event name to the Rhesis equivalent.

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


def _to_json_text(value: Any) -> str:
    """Render a tool I/O payload as JSON-friendly text.

    MAF stores ``gen_ai.tool.call.{arguments,result}`` as one of:

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


def is_handoff_tool_span(attributes: Mapping[str, Any]) -> bool:
    """Return True if this MAF span is a synthetic ``handoff_to_*`` tool call.

    MAF's ``HandoffBuilder`` workflow models agent-to-agent handoffs as
    auto-generated tool calls of the form ``handoff_to_<target_agent>``.
    These are emitted as ordinary ``execute_tool`` spans, but they don't
    represent real domain tools — they're scheduling artefacts. Recognising
    them lets the translator re-emit them as ``ai.agent.handoff`` spans so
    multi-agent UIs (e.g. the Rhesis Graph View) can draw the right edges.
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_EXECUTE_TOOL:
        return False
    tool_name = attributes.get(GEN_AI_TOOL_NAME)
    return isinstance(tool_name, str) and tool_name.startswith(HANDOFF_TOOL_PREFIX)


def handoff_target_name(attributes: Mapping[str, Any]) -> str:
    """Extract the destination agent name from a handoff tool span.

    ``handoff_to_math_specialist`` -> ``math_specialist``. Falls back to the
    raw tool name when the prefix is unexpectedly missing, and to an empty
    string when ``gen_ai.tool.name`` is absent.
    """
    tool_name = attributes.get(GEN_AI_TOOL_NAME)
    if not isinstance(tool_name, str):
        return ""
    if tool_name.startswith(HANDOFF_TOOL_PREFIX):
        return tool_name[len(HANDOFF_TOOL_PREFIX) :]
    return tool_name


def extract_handoff_targets_from_messages(attributes: Mapping[str, Any]) -> list[str]:
    """Extract handoff target agent ids from a chat span's output messages.

    MAF's ``HandoffBuilder`` short-circuits ``handoff_to_*`` tool calls via
    ``_AutoHandoffMiddleware`` (it raises ``MiddlewareTermination`` before the
    function-invocation span is ever created), so no ``execute_tool
    handoff_to_*`` span is emitted. The only place the handoff is observable is
    the chat span's ``gen_ai.output.messages`` attribute, where the model's
    handoff decision is recorded as an assistant ``tool_call`` part::

        [{"role": "assistant",
          "parts": [{"type": "tool_call",
                     "name": "handoff_to_<target>", "arguments": "{}"}]}]

    This helper decodes those output messages and returns the stripped target
    agent ids (``handoff_to_destination_finder`` -> ``destination_finder``) so
    the translator can synthesize ``ai.agent.handoff`` spans the Graph View can
    connect.

    Only applies to chat spans (``gen_ai.operation.name == "chat"``). Returns
    an empty list for non-chat spans, when no output messages are present
    (e.g. content capture disabled), or when no handoff tool calls are found.
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_CHAT:
        return []

    messages = _coerce_message_list(attributes.get(GEN_AI_OUTPUT_MESSAGES))
    if not messages:
        return []

    targets: list[str] = []
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") != "tool_call":
                continue
            name = part.get("name")
            if isinstance(name, str) and name.startswith(HANDOFF_TOOL_PREFIX):
                target = name[len(HANDOFF_TOOL_PREFIX) :].strip()
                if target:
                    targets.append(target)
    return targets


# Original MAF span-name prefixes for low-value workflow infrastructure spans.
# These are routing/transport/construction primitives that carry no
# agent/chat/tool payload and never *parent* a meaningful span:
#
# - ``edge_group.`` / ``message.send`` are routing primitives that use OTel
#   links rather than nesting for causality (see
#   ``agent_framework.observability.create_edge_group_processing_span``).
# - ``workflow.build`` wraps graph validation/compilation at
#   ``WorkflowBuilder.build()`` time. It is emitted *outside* any
#   ``workflow.run`` span, so it surfaces as its own standalone (and otherwise
#   empty) trace — one extra root per build. Its only children would be the
#   ``build.*`` events it records itself; agents are constructed before
#   ``.build()`` and are not nested under it. Dropping it keeps each workflow
#   run a single trace instead of a build-trace plus a run-trace.
#
# Dropping these sharply reduces span volume for fan-out topologies (e.g. MAF's
# ``HandoffBuilder`` broadcasts to every participant each superstep) without
# orphaning children. Note: ``executor.process`` is deliberately NOT here — it
# is the structural parent of ``invoke_agent`` spans, and ``workflow.run`` is
# kept because it is the run's trace root.
_LOW_VALUE_WORKFLOW_PREFIXES: tuple[str, ...] = (
    "edge_group.",
    "message.send",
    "workflow.build",
)


def is_low_value_workflow_span(original_name: str | None) -> bool:
    """Return True for MAF workflow spans safe to drop as noise.

    Matches the *original* (pre-translation) MAF span name against
    :data:`_LOW_VALUE_WORKFLOW_PREFIXES`. The translator uses this to skip
    forwarding edge-group / message-send routing spans unless the caller opts
    back in (see ``RHESIS_MAF_VERBOSE_WORKFLOW_SPANS``).
    """
    if not original_name:
        return False
    return any(original_name.startswith(prefix) for prefix in _LOW_VALUE_WORKFLOW_PREFIXES)


def translate_handoff_attributes(
    attributes: Mapping[str, Any],
    *,
    from_agent: str | None,
) -> dict[str, Any]:
    """Build the attribute set for a synthetic ``ai.agent.handoff`` span.

    Preserves every original ``gen_ai.*`` attribute (passthrough) and stamps
    the Rhesis handoff attributes on top:

    - ``ai.operation.type`` = ``agent.handoff``
    - ``ai.agent.handoff.to`` = parsed destination agent
    - ``ai.agent.handoff.from`` = the agent that emitted the handoff tool
      call, when known (caller resolves this from the OTel parent chain).

    ``from_agent`` is optional because in adversarial cases (e.g. the
    invoke_agent ancestor span is in a different export batch) we may not
    have it. We still emit the span with ``to`` set so the trace tree stays
    debuggable; the Graph View needs both ``from`` and ``to`` to draw an
    edge but the underlying span and event data are still useful.
    """
    translated: dict[str, Any] = dict(attributes)
    translated[AIAttributes.OPERATION_TYPE] = AIAttributes.OPERATION_AGENT_HANDOFF
    to_agent = handoff_target_name(attributes)
    if to_agent:
        translated.setdefault(AIAttributes.AGENT_HANDOFF_TO, to_agent)
    if from_agent:
        translated.setdefault(AIAttributes.AGENT_HANDOFF_FROM, from_agent)
    return translated


def _coerce_message_list(value: Any) -> list[Any] | None:
    """Decode a ``gen_ai.*.messages`` attribute into a list, defensively.

    MAF stores the value as a JSON-encoded string, but tolerate an
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


def _join_message_parts(parts: Any) -> str:
    """Render a message's ``parts`` list into a single display string.

    Text and reasoning parts are concatenated verbatim; non-text parts (tool
    calls, blobs, ...) are JSON-encoded so they remain visible rather than
    dropped. Falls back to an empty string for unexpected shapes.
    """
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return _to_json_text(parts) if parts is not None else ""

    chunks: list[str] = []
    for part in parts:
        if isinstance(part, Mapping):
            part_type = part.get("type")
            if part_type in ("text", "reasoning"):
                content = part.get("content")
                if content is not None:
                    chunks.append(content if isinstance(content, str) else _to_json_text(content))
                continue
            chunks.append(_to_json_text(part))
        elif isinstance(part, str):
            chunks.append(part)
        elif part is not None:
            chunks.append(_to_json_text(part))
    return "".join(chunks)


def _join_text_parts(parts: Any) -> str:
    """Concatenate only the human-readable ``text``/``reasoning`` parts.

    Unlike :func:`_join_message_parts`, non-text parts (tool calls, blobs, ...)
    are skipped rather than JSON-encoded. Used for conversation input/output
    capture, where we want the user's query and the assistant's prose answer,
    not the JSON of a ``handoff_to_*`` tool call.
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


def is_workflow_run_span(original_name: str | None) -> bool:
    """Return True for MAF's top-level ``workflow.run`` span (the run root)."""
    return original_name == WORKFLOW_RUN_SPAN_NAME


def extract_conversation_input(attributes: Mapping[str, Any]) -> str | None:
    """Return the original user query text from a chat span's input messages.

    Reads ``gen_ai.input.messages`` and returns the text of the first
    ``role == "user"`` message. Within a single workflow run every agent's chat
    span carries the same original user message as the first user entry, so the
    caller can record the first non-empty result and treat it as the turn input.
    Returns ``None`` for non-chat spans, missing/empty content, or when capture
    is disabled.
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_CHAT:
        return None
    messages = _coerce_message_list(attributes.get(GEN_AI_INPUT_MESSAGES))
    if not messages:
        return None
    for message in messages:
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        content = _join_text_parts(message.get("parts")).strip()
        if content:
            return content
    return None


def extract_conversation_output(attributes: Mapping[str, Any]) -> str | None:
    """Return the assistant response text from a chat span's output messages.

    Reads ``gen_ai.output.messages`` and joins the text parts of every output
    message. Tool-call-only turns (e.g. a ``handoff_to_*`` decision) yield an
    empty string and are skipped. The caller records the latest non-empty
    result per run, so the final synthesizing agent's answer is what remains.
    Returns ``None`` for non-chat spans or when there is no text output.
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_CHAT:
        return None
    messages = _coerce_message_list(attributes.get(GEN_AI_OUTPUT_MESSAGES))
    if not messages:
        return None
    chunks: list[str] = []
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        content = _join_text_parts(message.get("parts")).strip()
        if content:
            chunks.append(content)
    joined = "\n".join(chunks).strip()
    return joined or None


def synthesize_message_events(
    attributes: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Build ``ai.prompt`` / ``ai.completion`` events from MAF message attrs.

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

    system_instructions = _coerce_message_list(attributes.get(GEN_AI_SYSTEM_INSTRUCTIONS))
    if system_instructions:
        content = _join_message_parts(system_instructions)
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

    input_messages = _coerce_message_list(attributes.get(GEN_AI_INPUT_MESSAGES))
    for message in input_messages or ():
        if not isinstance(message, Mapping):
            continue
        content = _join_message_parts(message.get("parts"))
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

    output_messages = _coerce_message_list(attributes.get(GEN_AI_OUTPUT_MESSAGES))
    if output_messages:
        completion_chunks: list[str] = []
        for message in output_messages:
            if not isinstance(message, Mapping):
                continue
            content = _join_message_parts(message.get("parts"))
            if content:
                completion_chunks.append(content)
        joined = "\n".join(completion_chunks).strip()
        if joined:
            events.append(("ai.completion", {AIAttributes.COMPLETION_CONTENT: joined}))

    return events


def synthesize_tool_io_events(
    attributes: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Build synthetic ``ai.tool.input``/``ai.tool.output`` events from MAF attrs.

    MAF stores tool arguments and results as span *attributes* rather than as
    span events; the Rhesis backend renders them as events. This helper
    produces the events the translator should attach in addition to those
    already emitted by MAF.
    """
    events: list[tuple[str, dict[str, Any]]] = []
    args = attributes.get(GEN_AI_TOOL_CALL_ARGS)
    if args is not None:
        events.append(("ai.tool.input", {AIAttributes.TOOL_INPUT_CONTENT: _to_json_text(args)}))
    result = attributes.get(GEN_AI_TOOL_CALL_RESULT)
    if result is not None:
        events.append(("ai.tool.output", {AIAttributes.TOOL_OUTPUT_CONTENT: _to_json_text(result)}))
    return events
