"""Pure-data translation tables for Pydantic AI spans.

Pydantic AI's built-in instrumentation emits spans following the OpenTelemetry
GenAI semantic conventions, with span names like ``"invoke_agent assistant"``
/ ``"chat gpt-4o"`` / ``"execute_tool calculator"`` and attributes in the
``gen_ai.*`` namespace (verified empirically against pydantic-ai 2.0.0 at
instrumentation version 5).

The framework-neutral parts of the ``gen_ai.*`` -> ``ai.*`` bridge (constants,
attribute/event translation, message-event synthesis) live in
:mod:`rhesis.sdk.telemetry.integrations.genai`; this module owns only what is
Pydantic-AI-specific:

- the ``pydantic-ai`` instrumentation scope check,
- span-name mapping with a ``function.pydantic_ai.*`` fallback,
- agent-run span extras (``gen_ai.aggregated_usage.*`` token totals,
  ``final_result`` completion events, ``pydantic_ai.all_messages`` prompts).

The functions here are deliberately pure: no OTEL imports, no side effects.
That makes them trivial to unit test.
"""

from __future__ import annotations

from typing import Any, Mapping

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.integrations.genai import (  # noqa: F401
    GEN_AI_AGENT_NAME,
    GEN_AI_OPERATION_NAME,
    OP_CHAT,
    OP_CREATE_AGENT,
    OP_EXECUTE_TOOL,
    OP_INVOKE_AGENT,
    coerce_message_list,
    join_text_parts,
)
from rhesis.sdk.telemetry.integrations.genai import (
    translate_attributes as _translate_genai_attributes,
)
from rhesis.telemetry.schemas import AIOperationType

# Pydantic AI's instrumentation scope (InstrumentationSettings tracer name).
INSTRUMENTATION_SCOPE_PREFIX = "pydantic-ai"

# Pydantic-AI-specific span attributes (beyond the shared gen_ai.* set).
# Agent-run (invoke_agent) spans aggregate token usage across every model
# request the run made, under a different key than per-request usage.
GEN_AI_AGGREGATED_USAGE_INPUT_TOKENS = "gen_ai.aggregated_usage.input_tokens"
GEN_AI_AGGREGATED_USAGE_OUTPUT_TOKENS = "gen_ai.aggregated_usage.output_tokens"
# The run's final output, already JSON-rendered for structured outputs.
FINAL_RESULT = "final_result"
# The full message history of the run as a JSON array (same parts shape as
# gen_ai.input.messages).
PYDANTIC_AI_ALL_MESSAGES = "pydantic_ai.all_messages"
# Plain (non-namespaced) duplicates Pydantic AI stamps on agent spans.
MODEL_NAME = "model_name"

# Operation -> Rhesis span name. Pydantic AI emits chat / invoke_agent /
# execute_tool today; create_agent is included defensively for parity with the
# GenAI conventions.
_OPERATION_TO_SPAN_NAME: Mapping[str, str] = {
    OP_CHAT: AIOperationType.LLM_INVOKE,
    OP_INVOKE_AGENT: "ai.agent.invoke",
    OP_CREATE_AGENT: "ai.agent.invoke",
    OP_EXECUTE_TOOL: AIOperationType.TOOL_INVOKE,
}


def is_pydantic_ai_scope(scope_name: str | None) -> bool:
    """Return True if the OTEL instrumentation scope belongs to Pydantic AI."""
    if not scope_name:
        return False
    return scope_name.startswith(INSTRUMENTATION_SCOPE_PREFIX)


def translate_span_name(original_name: str, attributes: Mapping[str, Any]) -> str:
    """Translate a Pydantic AI span name to the Rhesis ``ai.*`` schema.

    Prefers the explicit ``gen_ai.operation.name`` attribute (precise) and
    falls back to scanning the original span name (fuzzy). If neither path
    matches, the name is sanitized into the ``function.pydantic_ai.*``
    namespace so it always satisfies
    :func:`rhesis.sdk.telemetry.attributes.validate_span_name`. This protects
    the integration against Pydantic AI adding new operations under us.
    """
    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if isinstance(operation, str) and operation in _OPERATION_TO_SPAN_NAME:
        return _OPERATION_TO_SPAN_NAME[operation]

    # Fuzzy fallback: the name starts with a known operation token
    if original_name:
        leading = original_name.split(" ", 1)[0]
        if leading in _OPERATION_TO_SPAN_NAME:
            return _OPERATION_TO_SPAN_NAME[leading]

    return fallback_function_pydantic_ai_name(original_name)


def fallback_function_pydantic_ai_name(original_name: str) -> str:
    """Last-resort name sanitizer that always satisfies ``validate_span_name``.

    The Rhesis backend rejects anything that is not ``ai.<domain>(.<action>)?``
    or ``function.<...>``. Names like ``"chat gpt-4o"`` (with a space) or a
    brand-new Pydantic AI operation we have not mapped would otherwise fail
    validation and be dropped with HTTP 422. Funneling unknowns into
    ``function.pydantic_ai.*`` keeps them visible in the trace tree without
    claiming a specific ``ai.*`` semantic.
    """
    if not original_name:
        return "function.pydantic_ai.unknown"
    sanitized = original_name.replace(" ", "_").replace(".", "_").lower()
    return f"function.pydantic_ai.{sanitized}"


def translate_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Build the translated attribute set for a Pydantic AI span.

    Extends the shared GenAI translation with Pydantic-AI-specific extras:

    - ``gen_ai.aggregated_usage.*`` (agent-run spans aggregate usage across
      every model request in the run) maps to the same ``ai.llm.tokens.*``
      attributes that per-request usage does on chat spans.
    - the plain ``model_name`` attribute maps to ``ai.model.name`` (agent
      spans carry it instead of ``gen_ai.request.model``).
    """
    translated = _translate_genai_attributes(attributes)

    input_tokens = attributes.get(GEN_AI_AGGREGATED_USAGE_INPUT_TOKENS)
    output_tokens = attributes.get(GEN_AI_AGGREGATED_USAGE_OUTPUT_TOKENS)
    if input_tokens is not None:
        translated.setdefault(AIAttributes.LLM_TOKENS_INPUT, input_tokens)
    if output_tokens is not None:
        translated.setdefault(AIAttributes.LLM_TOKENS_OUTPUT, output_tokens)
    if input_tokens is not None or output_tokens is not None:
        total = (input_tokens or 0) + (output_tokens or 0)
        translated.setdefault(AIAttributes.LLM_TOKENS_TOTAL, total)

    model_name = attributes.get(MODEL_NAME)
    if model_name is not None:
        translated.setdefault(AIAttributes.MODEL_NAME, model_name)

    return translated


def synthesize_agent_events(
    attributes: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Build ``ai.prompt`` / ``ai.completion`` events for an agent-run span.

    Pydantic AI's ``invoke_agent`` spans carry the run's input and output as
    attributes (``pydantic_ai.all_messages`` and ``final_result``) rather than
    as span events. Synthesizing a prompt event from the first user message
    and a completion event from the final result keeps the agent span
    self-contained in the Rhesis trace UI, matching what the previous
    ``Agent.run``-patching integration recorded.

    Only applies to agent spans (``gen_ai.operation.name == "invoke_agent"``);
    chat spans get their message events from the shared
    :func:`~rhesis.sdk.telemetry.integrations.genai.synthesize_message_events`
    instead. Returns an empty list when no usable content is present (e.g.
    content capture disabled).
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_INVOKE_AGENT:
        return []

    events: list[tuple[str, dict[str, Any]]] = []

    messages = coerce_message_list(attributes.get(PYDANTIC_AI_ALL_MESSAGES))
    for message in messages or ():
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        content = join_text_parts(message.get("parts")).strip()
        if content:
            events.append(
                (
                    "ai.prompt",
                    {
                        AIAttributes.PROMPT_ROLE: "user",
                        AIAttributes.PROMPT_CONTENT: content,
                    },
                )
            )
            break

    final_result = attributes.get(FINAL_RESULT)
    if isinstance(final_result, str) and final_result:
        events.append(("ai.completion", {AIAttributes.COMPLETION_CONTENT: final_result}))

    return events
