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

from typing import Any, Mapping

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import AIOperationType

INSTRUMENTATION_SCOPE_PREFIX = "agent_framework"

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
        events.append(("ai.tool.input", {AIAttributes.TOOL_INPUT_CONTENT: str(args)}))
    result = attributes.get(GEN_AI_TOOL_CALL_RESULT)
    if result is not None:
        events.append(("ai.tool.output", {AIAttributes.TOOL_OUTPUT_CONTENT: str(result)}))
    return events
