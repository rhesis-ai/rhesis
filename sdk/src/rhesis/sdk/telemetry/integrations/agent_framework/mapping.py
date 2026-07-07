"""Pure-data translation tables for Microsoft Agent Framework spans.

Microsoft Agent Framework (MAF) emits spans following the OpenTelemetry GenAI
semantic conventions, with span names like ``"chat gpt-4"`` /
``"invoke_agent assistant"`` / ``"execute_tool calculator"`` and attributes in
the ``gen_ai.*`` namespace.

The Rhesis backend, by contrast, expects span names from the ``ai.*`` /
``function.*`` namespaces (see :mod:`rhesis.sdk.telemetry.attributes`). The
framework-neutral parts of that bridge (GenAI constants, attribute/event
translation, message-event synthesis) live in
:mod:`rhesis.sdk.telemetry.integrations.genai` and are re-exported here so
existing imports keep working; this module owns only what is MAF-specific
(workflow spans, ``handoff_to_*`` tool heuristics, span-name mapping).

The functions here are deliberately pure: no OTEL imports, no side effects.
That makes them trivial to unit test.
"""

from __future__ import annotations

from typing import Any, Mapping

from rhesis.sdk.telemetry.attributes import AIAttributes

# Framework-neutral GenAI pieces, re-exported under their historical names so
# the translator and tests keep working unchanged. New MAF-specific helpers
# should keep living in this module; new shared helpers belong in genai.py.
from rhesis.sdk.telemetry.integrations.genai import (  # noqa: F401
    EVENT_ASSISTANT_MESSAGE,
    EVENT_CHOICE,
    EVENT_SYSTEM_MESSAGE,
    EVENT_TOOL_MESSAGE,
    EVENT_USER_MESSAGE,
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_CALL_ARGS,
    GEN_AI_TOOL_CALL_RESULT,
    GEN_AI_TOOL_DESCRIPTION,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    OP_CHAT,
    OP_CREATE_AGENT,
    OP_EMBEDDINGS,
    OP_EXECUTE_TOOL,
    OP_INVOKE_AGENT,
    extract_conversation_input,
    extract_conversation_output,
    synthesize_message_events,
    synthesize_tool_io_events,
    translate_attributes,
    translate_event_attributes,
    translate_event_name,
)
from rhesis.sdk.telemetry.integrations.genai import (
    coerce_message_list as _coerce_message_list,
)
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


def is_workflow_run_span(original_name: str | None) -> bool:
    """Return True for MAF's top-level ``workflow.run`` span (the run root)."""
    return original_name == WORKFLOW_RUN_SPAN_NAME
