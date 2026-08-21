"""Pure-data translation tables for Google ADK spans.

Google ADK (``google-adk``) emits OpenTelemetry spans natively under the
instrumentation scope ``gcp.vertex.agent``, partly following the GenAI semantic
conventions (``gen_ai.*``) and partly using its own ``gcp.vertex.agent.*``
namespace. The Rhesis backend expects the ``ai.*`` / ``function.*`` schema
instead (see :mod:`rhesis.telemetry.attributes`).

The framework-neutral parts of that bridge live in
:mod:`rhesis.sdk.telemetry.integrations.genai`; this module owns what is
ADK-specific:

- the span-name map, covering **both** ADK telemetry schema versions,
- the ADK-proprietary attribute names,
- extraction of prompts / completions / tool I/O out of the JSON blobs ADK
  stores in ``gcp.vertex.agent.llm_request`` / ``.llm_response`` /
  ``.tool_call_args`` / ``.tool_response``,
- handoff detection for ADK's two multi-agent mechanisms, and
- the low-value-span list.

Where ADK differs from the frameworks ``genai.py`` was written for:

- ADK does **not** emit ``gen_ai.input.messages`` / ``gen_ai.output.messages``
  by default, so the shared message-event synthesis finds nothing. It only does
  so when the app opts into the experimental GenAI semconv, which is a *global*
  OTel switch we deliberately never set ourselves.
- ``gen_ai.system`` on the ``call_llm`` span is the literal string
  ``"gcp.vertex.agent"`` -- a framework label, not a model provider. The shared
  attribute map would route it straight into ``ai.model.provider``, so
  :func:`translate_attributes` overwrites it.
- ADK's model-call operation is ``generate_content``, not ``chat``.

The functions here are deliberately pure: no OTEL imports, no side effects.
That makes them trivial to unit test.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable, Mapping

# Framework-neutral GenAI pieces, imported under their public names (the
# ``pydantic_ai`` style). New ADK-specific helpers stay in this module; new
# shared helpers belong in genai.py.
from rhesis.sdk.telemetry.integrations.genai import (
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_REQUEST_MODEL,
    # Re-exported: ADK sets ``gen_ai.system`` to the literal framework label
    # ``gcp.vertex.agent`` on ``call_llm``, which is the quirk
    # :func:`translate_attributes` has to undo.
    GEN_AI_SYSTEM,  # noqa: F401
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_NAME,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    OP_CHAT,
    OP_EXECUTE_TOOL,
    OP_INVOKE_AGENT,
    TRUTHY_ENV_VALUES,
    to_json_text,
)
from rhesis.sdk.telemetry.integrations.genai import (
    extract_conversation_input as _semconv_conversation_input,
)
from rhesis.sdk.telemetry.integrations.genai import (
    extract_conversation_output as _semconv_conversation_output,
)
from rhesis.sdk.telemetry.integrations.genai import (
    synthesize_message_events as _synthesize_semconv_message_events,
)
from rhesis.sdk.telemetry.integrations.genai import (
    translate_attributes as _translate_genai_attributes,
)
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import AIOperationType

# ADK's single instrumentation scope. Note it is *not* ``google.adk``: ADK calls
# ``trace.get_tracer(instrumenting_module_name="gcp.vertex.agent", ...)``, so a
# ``startswith("google")`` check would match nothing.
INSTRUMENTATION_SCOPE = "gcp.vertex.agent"

# ---------------------------------------------------------------------------
# ADK span names
# ---------------------------------------------------------------------------

# Schema v1 trace root. Carries *zero* attributes -- not even a session id.
# It is also NOT unique per trace: ``AgentTool`` builds its own inner ``Runner``,
# which emits a second, nested ``invocation``. Never treat the name as "the turn
# root"; use "is the trace root" instead.
INVOCATION_SPAN_NAME = "invocation"

# The outer of ADK's two model-call spans. Present under both schema versions
# (``_schema_version.py`` lists its removal as an unshipped migration step) and
# the only one that carries prompt/completion content with default settings.
CALL_LLM_SPAN_NAME = "call_llm"

# The inner model-call span, ``generate_content {model}``. A 1:1 child of
# ``call_llm`` that duplicates it, so it is dropped and its children are
# re-pointed at ``call_llm`` -- see the translator. It is promoted to the
# ``ai.llm.invoke`` span only when no ``call_llm`` ancestor exists.
GENERATE_CONTENT_SPAN_PREFIX = "generate_content"

INVOKE_AGENT_SPAN_PREFIX = "invoke_agent"
INVOKE_WORKFLOW_SPAN_PREFIX = "invoke_workflow"
INVOKE_NODE_SPAN_PREFIX = "invoke_node"
EXECUTE_TOOL_SPAN_PREFIX = "execute_tool"

# The ``invoke_agent `` prefix (with the trailing space) that
# :class:`~rhesis.sdk.telemetry.integrations.genai.AncestryRegistry` splits on to
# read an agent's name out of its span name at span-start time.
INVOKE_AGENT_NAME_PREFIX = f"{INVOKE_AGENT_SPAN_PREFIX} "

# ADK's ``sub_agents`` handoff primitive. The model calls a built-in tool of
# this exact name with ``{"agent_name": "<target>"}``; the target agent's own
# ``invoke_agent`` span is emitted as a *sibling* of the caller's, not a child,
# so this tool span is the only place the edge is observable.
TRANSFER_TOOL_NAME = "transfer_to_agent"

# ---------------------------------------------------------------------------
# ADK operation values and proprietary attributes
# ---------------------------------------------------------------------------

OP_GENERATE_CONTENT = "generate_content"
OP_INVOKE_WORKFLOW = "invoke_workflow"
OP_INVOKE_NODE = "invoke_node"

# ``gen_ai.operation.name`` values that mean "a model call" for the shared
# helpers, which default to ``chat`` only.
ADK_CHAT_OPERATIONS: tuple[str, ...] = (OP_CHAT, OP_GENERATE_CONTENT)

GCP_LLM_REQUEST = "gcp.vertex.agent.llm_request"
GCP_LLM_RESPONSE = "gcp.vertex.agent.llm_response"
GCP_TOOL_CALL_ARGS = "gcp.vertex.agent.tool_call_args"
GCP_TOOL_RESPONSE = "gcp.vertex.agent.tool_response"
GCP_DATA = "gcp.vertex.agent.data"
GCP_SESSION_ID = "gcp.vertex.agent.session_id"
GCP_INVOCATION_ID = "gcp.vertex.agent.invocation_id"
GCP_EVENT_ID = "gcp.vertex.agent.event_id"

GEN_AI_WORKFLOW_NAME = "gen_ai.workflow.name"
GEN_AI_WORKFLOW_NESTED = "gen_ai.workflow.nested"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"
GEN_AI_USAGE_REASONING_OUTPUT_TOKENS = "gen_ai.usage.reasoning.output_tokens"

# Stamped on a span that fell through to the ``function.google_adk.*`` fallback,
# so the original ADK name is still recoverable in the trace UI.
ORIGINAL_SPAN_NAME = "gen_ai.original_span_name"

# The big JSON payload attributes. Their content is re-emitted as ``ai.prompt`` /
# ``ai.completion`` / ``ai.tool.*`` events in the shape the trace UI reads, so
# forwarding the blobs too would ship the same text twice plus the entire
# tool-schema ``config`` on every single model call.
_CONTENT_BLOB_ATTRIBUTES: tuple[str, ...] = (
    GCP_LLM_REQUEST,
    GCP_LLM_RESPONSE,
    GCP_TOOL_CALL_ARGS,
    GCP_TOOL_RESPONSE,
    GCP_DATA,
)

# Values ADK writes into the content attributes when it has nothing real to say.
# ``"N/A"`` and ``"<not serializable>"`` both come from the merged-tool-call
# path; ``"<not specified>"`` is the missing-function-response fallback.
_CONTENT_SENTINELS: frozenset[str] = frozenset(
    {"", "{}", "[]", "N/A", "<not serializable>", "<not specified>"}
)

# The literal ADK writes for a tool whose function response could not be read.
_NOT_SPECIFIED_RESULT = {"result": "<not specified>"}

# ---------------------------------------------------------------------------
# Span-name mapping
# ---------------------------------------------------------------------------

# ``gen_ai.operation.name`` -> Rhesis span name. ``validate_span_name`` accepts
# ``ai.<domain>(.<action>)?`` (lowercase letters only) and anything starting with
# ``function.``, and it forbids ``chain`` / ``workflow`` / ``pipeline`` as the
# ``ai.*`` domain -- which is why ADK's workflow/node spans land under
# ``function.google_adk.*`` rather than ``ai.workflow.*``.
_OPERATION_TO_SPAN_NAME: Mapping[str, str] = {
    OP_INVOKE_AGENT: AIOperationType.AGENT_INVOKE.value,
    OP_EXECUTE_TOOL: AIOperationType.TOOL_INVOKE.value,
    OP_GENERATE_CONTENT: AIOperationType.LLM_INVOKE.value,
}

# Original span-name prefix -> ``function.google_adk.*`` namespace. Applied when
# the operation attribute is absent or unknown. The prefix's tail (a workflow or
# node name) is kept because it is low-cardinality and useful in the waterfall.
_NAME_PREFIX_MAP: Mapping[str, str] = {
    INVOKE_WORKFLOW_SPAN_PREFIX: "function.google_adk.workflow",
    INVOKE_NODE_SPAN_PREFIX: "function.google_adk.node",
}

# Original ADK span names that carry no agent/model/tool payload worth a row.
#
# - ``execute_tool (merged)`` is emitted *in addition to* the real per-tool spans
#   after a parallel function call, purely so ADK's own dev UI has something to
#   show. Its payload is worthless: ``gen_ai.tool.name`` is the literal
#   ``"(merged tools)"``, ``tool_call_args`` is the literal ``"N/A"``, and
#   ``tool_response`` is always ``"<not serializable>"`` because ADK 2.6 calls a
#   misspelled ``model_dumps_json``.
# - ``send_data`` (live/bidi), ``compact_events`` (history compaction),
#   ``handle_context_caching`` and ``create_cache`` are infrastructure.
#
# None of these parent a meaningful span, so dropping them cannot orphan
# anything. ``managed_agent_interaction`` is deliberately NOT here: it wraps a
# real agent interaction and can parent spans we care about.
_LOW_VALUE_SPAN_NAMES: tuple[str, ...] = (
    "execute_tool (merged)",
    "send_data",
    "compact_events",
    "handle_context_caching",
    "create_cache",
)


def is_adk_scope(scope_name: str | None) -> bool:
    """Return True if the OTEL instrumentation scope belongs to Google ADK.

    Matched exactly rather than by prefix. ADK's ``AutoTracingPlugin`` uses
    ``trace.get_tracer(__name__)`` instead, i.e. scope
    ``google.adk.plugins.auto_tracing_plugin``; those spans wrap arbitrary user
    functions rather than agent semantics, so we leave them alone.
    """
    return scope_name == INSTRUMENTATION_SCOPE


def translate_span_name(original_name: str, attributes: Mapping[str, Any]) -> str:
    """Translate an ADK span name to the Rhesis ``ai.*`` / ``function.*`` schema.

    Prefers the explicit ``gen_ai.operation.name`` attribute, then falls back to
    the leading token of the span name, then to the ``function.google_adk.*``
    namespace. One table serves both ADK telemetry schema versions: the only
    v1/v2 difference is *which* span is the trace root, and the translator
    decides that from ``span.parent`` rather than from the name.

    Args:
        original_name: The span name ADK assigned (e.g. ``"invoke_agent bot"``).
        attributes: The span's attribute map.

    Returns:
        A Rhesis-shaped span name (always either ``ai.*`` or ``function.*``).
    """
    # ``call_llm`` carries no ``gen_ai.operation.name`` at all, so it is matched
    # by name before anything else.
    if original_name == CALL_LLM_SPAN_NAME:
        return AIOperationType.LLM_INVOKE.value

    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if isinstance(operation, str):
        # A handoff needs a destination to be worth anything -- the Graph View
        # draws nothing without one. The target lives in the tool's arguments, so
        # with content capture off it is unknowable and an honest
        # ``ai.tool.invoke`` beats an edgeless ``ai.agent.handoff``.
        if (
            operation == OP_EXECUTE_TOOL
            and is_transfer_tool_span(attributes)
            and transfer_target(attributes)
        ):
            return AIOperationType.AGENT_HANDOFF.value
        if operation in _OPERATION_TO_SPAN_NAME:
            return _OPERATION_TO_SPAN_NAME[operation]

    if original_name:
        leading = original_name.split(" ", 1)[0]
        if leading in _OPERATION_TO_SPAN_NAME:
            return _OPERATION_TO_SPAN_NAME[leading]
        replacement = _NAME_PREFIX_MAP.get(leading)
        if replacement is not None:
            tail = _sanitize_name_segment(original_name[len(leading) :])
            return f"{replacement}.{tail}" if tail else replacement

    return fallback_function_adk_name(original_name)


def fallback_function_adk_name(original_name: str) -> str:
    """Last-resort name sanitizer that always satisfies ``validate_span_name``.

    The Rhesis backend rejects any span name that is not
    ``ai.<domain>(.<action>)?`` or ``function.<...>``, dropping it with HTTP 422.
    Raw ADK names like ``"invoke_agent root_agent"`` or ``"execute_tool
    (merged)"`` would all fail that check, so anything we have not mapped --
    including a span name a future ADK release invents under us -- is funnelled
    into ``function.google_adk.*``, which the validator accepts unconditionally.

    Also used by the exporter as the fallback name when translation raises.
    """
    if not original_name:
        return "function.google_adk.unknown"
    sanitized = _sanitize_name_segment(original_name)
    return f"function.google_adk.{sanitized}" if sanitized else "function.google_adk.unknown"


def _sanitize_name_segment(segment: str) -> str:
    """Reduce an arbitrary span-name tail to a safe ``function.*`` segment."""
    sanitized = segment.strip().lower()
    for char in " .()[]{}/\\:,":
        sanitized = sanitized.replace(char, "_")
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_")


def infra_span_name(original_name: str) -> str:
    """Name for an ADK infrastructure span kept only because verbose mode is on.

    These spans must never claim an ``ai.*`` semantic: ``generate_content`` would
    become a second ``ai.llm.invoke`` for a call already represented by
    ``call_llm``, and ``execute_tool (merged)`` would look like a real tool call.
    The model id is dropped from the model-span name because it is already on
    ``ai.model.name`` and would make the span name high-cardinality.
    """
    if is_model_span(original_name):
        return f"function.google_adk.{GENERATE_CONTENT_SPAN_PREFIX}"
    return fallback_function_adk_name(original_name)


def is_low_value_span(original_name: str | None) -> bool:
    """Return True for ADK infrastructure spans safe to drop as noise.

    Matches the *original* (pre-translation) ADK span name. The translator skips
    forwarding these unless the caller opts back in via
    ``RHESIS_GOOGLE_ADK_VERBOSE_SPANS``.
    """
    if not original_name:
        return False
    return any(original_name.startswith(name) for name in _LOW_VALUE_SPAN_NAMES)


def is_model_span(original_name: str | None) -> bool:
    """Return True for ADK's inner ``generate_content {model}`` span."""
    if not original_name:
        return False
    return original_name.split(" ", 1)[0] == GENERATE_CONTENT_SPAN_PREFIX


def is_call_llm_span(original_name: str | None) -> bool:
    """Return True for ADK's outer ``call_llm`` span."""
    return original_name == CALL_LLM_SPAN_NAME


def is_agent_span(attributes: Mapping[str, Any], original_name: str | None) -> bool:
    """Return True for an ``invoke_agent {name}`` span."""
    if attributes.get(GEN_AI_OPERATION_NAME) == OP_INVOKE_AGENT:
        return True
    if not original_name:
        return False
    return original_name.split(" ", 1)[0] == INVOKE_AGENT_SPAN_PREFIX


# ---------------------------------------------------------------------------
# Attribute translation
# ---------------------------------------------------------------------------

# Environment variables ADK itself consults to decide whether it is talking to
# Vertex AI rather than the Gemini API, in its own precedence order.
_ENTERPRISE_ENV_VARS: tuple[str, ...] = (
    "GOOGLE_GENAI_USE_ENTERPRISE",
    "GOOGLE_GENAI_USE_VERTEXAI",
)

# Model-id prefixes that mean "a Google first-party model".
_GOOGLE_MODEL_PREFIXES: tuple[str, ...] = ("gemini", "gemma")


def derive_model_provider(model: Any) -> str | None:
    """Derive ``ai.model.provider`` from an ADK model id.

    ADK gives us nothing usable for this. ``gen_ai.system`` on ``call_llm`` is
    hardcoded to the framework label ``"gcp.vertex.agent"``, and the copy on the
    ``generate_content`` span comes from ADK's ``_guess_gemini_system_name()``,
    which reports ``gemini``/``vertex_ai`` even for a LiteLLM-backed Anthropic
    model -- and is absent entirely on the experimental-semconv path.

    So we read the model id, which ADK sets verbatim from the agent's model:

    - ``projects/.../publishers/google/models/gemini-...`` -> ``vertex_ai``
    - any other ``<provider>/<model>`` -> the prefix, which is LiteLLM's
      convention (``openai/gpt-4o`` -> ``openai``, ``anthropic/...``)
    - ``gemini*`` / ``gemma*`` -> ``vertex_ai`` or ``gemini``, matching ADK
    - anything else -> ``None``, so we leave the attribute unset rather than
      claim a provider we guessed wrong.
    """
    if not isinstance(model, str):
        return None
    candidate = model.strip()
    if not candidate:
        return None
    if candidate.startswith("projects/"):
        return "vertex_ai"
    if "/" in candidate:
        prefix = candidate.split("/", 1)[0].strip()
        return prefix or None
    if candidate.lower().startswith(_GOOGLE_MODEL_PREFIXES):
        return "vertex_ai" if _enterprise_mode_enabled() else "gemini"
    return None


def _enterprise_mode_enabled() -> bool:
    for name in _ENTERPRISE_ENV_VARS:
        raw = os.getenv(name)
        if raw is not None:
            return raw.strip().lower() in TRUTHY_ENV_VALUES
    return False


def translate_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Build the translated attribute set for an ADK span.

    Runs the shared GenAI translation first, then applies the ADK-specific
    corrections: the extra operation values ADK invents, the token counters it
    reports separately, a real ``ai.model.provider``, and removal of the raw
    content blobs whose payload we re-emit as span events.
    """
    translated = _translate_genai_attributes(attributes)

    operation = attributes.get(GEN_AI_OPERATION_NAME)
    if operation == OP_GENERATE_CONTENT:
        translated.setdefault(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_LLM_INVOKE)
    elif operation in (OP_INVOKE_WORKFLOW, OP_INVOKE_NODE):
        translated.setdefault(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
    elif GCP_LLM_REQUEST in attributes and GEN_AI_REQUEST_MODEL in attributes:
        # ``call_llm`` sets no operation name of its own.
        translated.setdefault(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_LLM_INVOKE)

    _apply_token_attributes(attributes, translated)

    # Direct assignment, not setdefault: the shared map has already copied
    # ``gen_ai.system`` (the literal "gcp.vertex.agent") into this key.
    provider = derive_model_provider(attributes.get(GEN_AI_REQUEST_MODEL))
    if provider:
        translated[AIAttributes.MODEL_PROVIDER] = provider
    elif translated.get(AIAttributes.MODEL_PROVIDER) == INSTRUMENTATION_SCOPE:
        translated.pop(AIAttributes.MODEL_PROVIDER, None)

    # The ADK session id only ever appears under ``gcp.vertex.agent.session_id``
    # on ``call_llm``; every other span uses ``gen_ai.conversation.id``.
    resolved_session = session_id(attributes)
    if resolved_session:
        translated.setdefault(AIAttributes.SESSION_ID, resolved_session)

    for blob in _CONTENT_BLOB_ATTRIBUTES:
        translated.pop(blob, None)

    return translated


def _apply_token_attributes(attributes: Mapping[str, Any], translated: dict[str, Any]) -> None:
    """Fold ADK's extra token counters into the Rhesis token attributes.

    The shared helper only knows ``gen_ai.usage.input_tokens`` /
    ``.output_tokens``. ADK reports cached input and reasoning output separately,
    and already *includes* reasoning tokens in its output total (its
    ``TokenUsage`` sums ``candidates_token_count + thoughts_token_count``), so
    only the cache-read count still has to be added to reach a true total.
    """
    input_tokens = attributes.get(GEN_AI_USAGE_INPUT_TOKENS)
    output_tokens = attributes.get(GEN_AI_USAGE_OUTPUT_TOKENS)
    if input_tokens is None and output_tokens is None:
        return

    cache_read = attributes.get(GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS)
    if not isinstance(cache_read, int):
        cache_read = 0
    translated[AIAttributes.LLM_TOKENS_TOTAL] = (
        (input_tokens or 0) + (output_tokens or 0) + cache_read
    )


# ---------------------------------------------------------------------------
# Content extraction from ADK's JSON blobs
# ---------------------------------------------------------------------------

# google-genai uses "model" where the GenAI conventions (and the Rhesis trace
# UI) use "assistant".
_ROLE_ALIASES: Mapping[str, str] = {"model": "assistant"}


def _decode_blob(value: Any) -> Any | None:
    """Decode one of ADK's JSON blob attributes, defensively.

    Returns ``None`` for a missing value, one of ADK's sentinel strings, or
    malformed JSON, so callers can skip it without raising.
    """
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip() in _CONTENT_SENTINELS:
            return None
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    if isinstance(value, (Mapping, list)):
        return value or None
    return None


def _render_content_parts(parts: Any) -> str:
    """Render a google-genai ``Content.parts`` list for display.

    ``text`` parts are concatenated verbatim; everything else (function calls,
    function responses, file references) is JSON-encoded so it stays visible in
    the trace rather than silently disappearing.
    """
    if not isinstance(parts, list):
        return "" if parts is None else to_json_text(parts)
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, Mapping):
            if part is not None:
                chunks.append(to_json_text(part))
            continue
        text = part.get("text")
        if isinstance(text, str) and text:
            chunks.append(text)
            continue
        chunks.append(to_json_text(dict(part)))
    return "".join(chunks)


def _text_only_parts(parts: Any) -> str:
    """Concatenate only the ``text`` parts, skipping tool calls and blobs."""
    if not isinstance(parts, list):
        return ""
    return "".join(
        part["text"]
        for part in parts
        if isinstance(part, Mapping) and isinstance(part.get("text"), str)
    )


def _system_instruction_text(config: Any) -> str:
    """Extract the system instruction, which may be a string or a ``Content``."""
    if not isinstance(config, Mapping):
        return ""
    instruction = config.get("system_instruction")
    if isinstance(instruction, str):
        return instruction
    if isinstance(instruction, Mapping):
        return _render_content_parts(instruction.get("parts"))
    if isinstance(instruction, list):
        return _render_content_parts(instruction)
    return ""


def has_semconv_messages(attributes: Mapping[str, Any]) -> bool:
    """Return True if the span carries the standard GenAI message attributes.

    ADK only emits these when the app has opted into the experimental GenAI
    semconv (``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental``). We
    never set that switch ourselves -- it is global and changes behaviour in
    unrelated instrumentations -- but we prefer the attributes when they are
    there, because their structured parts beat parsing ADK's raw blobs.
    """
    return any(
        attributes.get(key)
        for key in (GEN_AI_INPUT_MESSAGES, GEN_AI_OUTPUT_MESSAGES, GEN_AI_SYSTEM_INSTRUCTIONS)
    )


def semconv_message_carrier(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Extract just the GenAI message attributes, tagged as a model call.

    ADK puts these on the ``generate_content`` span, which the translator drops.
    The dedup processor stashes this small dict against the parent ``call_llm``
    span so the surviving span can still render the content.
    """
    carrier: dict[str, Any] = {GEN_AI_OPERATION_NAME: OP_GENERATE_CONTENT}
    for key in (GEN_AI_INPUT_MESSAGES, GEN_AI_OUTPUT_MESSAGES, GEN_AI_SYSTEM_INSTRUCTIONS):
        value = attributes.get(key)
        if value:
            carrier[key] = value
    return carrier


def synthesize_llm_content_events(
    attributes: Mapping[str, Any],
    *,
    semconv_messages: Mapping[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Build ``ai.prompt`` / ``ai.completion`` events for a model-call span.

    Two sources, in preference order:

    1. the standard ``gen_ai.*.messages`` attributes, either handed over by the
       caller (they live on the dropped ``generate_content`` child) or present on
       this span -- translated by the shared helper;
    2. ADK's own ``gcp.vertex.agent.llm_request`` / ``.llm_response`` JSON blobs,
       which are populated by default.

    Returns an empty list when neither source has content, which is what happens
    with content capture turned off.
    """
    for carrier in (semconv_messages, attributes):
        if carrier and has_semconv_messages(carrier):
            return _synthesize_semconv_message_events(carrier, chat_operations=ADK_CHAT_OPERATIONS)

    events: list[tuple[str, dict[str, Any]]] = []
    request = _decode_blob(attributes.get(GCP_LLM_REQUEST))
    if isinstance(request, Mapping):
        system_text = _system_instruction_text(request.get("config"))
        if system_text:
            events.append(
                (
                    "ai.prompt",
                    {
                        AIAttributes.PROMPT_ROLE: "system",
                        AIAttributes.PROMPT_CONTENT: system_text,
                    },
                )
            )
        contents = request.get("contents")
        if isinstance(contents, list):
            for content in contents:
                if not isinstance(content, Mapping):
                    continue
                rendered = _render_content_parts(content.get("parts"))
                if not rendered:
                    continue
                role = content.get("role")
                role = role if isinstance(role, str) and role else "user"
                events.append(
                    (
                        "ai.prompt",
                        {
                            AIAttributes.PROMPT_ROLE: _ROLE_ALIASES.get(role, role),
                            AIAttributes.PROMPT_CONTENT: rendered,
                        },
                    )
                )

    response = _decode_blob(attributes.get(GCP_LLM_RESPONSE))
    if isinstance(response, Mapping):
        content = response.get("content")
        rendered = (
            _render_content_parts(content.get("parts")) if isinstance(content, Mapping) else ""
        )
        if rendered:
            events.append(("ai.completion", {AIAttributes.COMPLETION_CONTENT: rendered}))

    return events


def synthesize_tool_io_events(
    attributes: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Build ``ai.tool.input`` / ``ai.tool.output`` events for a tool span.

    ADK stores tool arguments and results as ``gcp.vertex.agent.tool_call_args``
    / ``.tool_response`` rather than the ``gen_ai.tool.call.*`` attributes the
    shared helper reads. Its several "nothing here" sentinels are skipped so we
    do not render ``N/A`` or ``<not serializable>`` as if they were tool output.
    """
    events: list[tuple[str, dict[str, Any]]] = []
    args = _decode_blob(attributes.get(GCP_TOOL_CALL_ARGS))
    if args is not None:
        events.append(("ai.tool.input", {AIAttributes.TOOL_INPUT_CONTENT: to_json_text(args)}))
    result = _decode_blob(attributes.get(GCP_TOOL_RESPONSE))
    if result is not None and result != _NOT_SPECIFIED_RESULT:
        events.append(("ai.tool.output", {AIAttributes.TOOL_OUTPUT_CONTENT: to_json_text(result)}))
    return events


def extract_conversation_input(
    attributes: Mapping[str, Any],
    *,
    semconv_messages: Mapping[str, Any] | None = None,
) -> str | None:
    """Return the user's query text from a model-call span.

    Reads the first ``role == "user"`` entry of the request blob (or of
    ``gen_ai.input.messages`` when available) and returns its text parts only --
    a tool-result turn also carries role ``user`` in google-genai's shape but has
    no text, so it is skipped naturally.
    """
    for carrier in (semconv_messages, attributes):
        if carrier and has_semconv_messages(carrier):
            return _semconv_conversation_input(carrier, chat_operations=ADK_CHAT_OPERATIONS)

    request = _decode_blob(attributes.get(GCP_LLM_REQUEST))
    if not isinstance(request, Mapping):
        return None
    contents = request.get("contents")
    if not isinstance(contents, list):
        return None
    for content in contents:
        if not isinstance(content, Mapping) or content.get("role") != "user":
            continue
        text = _text_only_parts(content.get("parts")).strip()
        if text:
            return text
    return None


def extract_conversation_output(
    attributes: Mapping[str, Any],
    *,
    semconv_messages: Mapping[str, Any] | None = None,
) -> str | None:
    """Return the assistant's prose answer from a model-call span.

    Text parts only: a turn whose response is a function call yields nothing, so
    tool-calling round trips do not overwrite the real answer.
    """
    for carrier in (semconv_messages, attributes):
        if carrier and has_semconv_messages(carrier):
            return _semconv_conversation_output(carrier, chat_operations=ADK_CHAT_OPERATIONS)

    response = _decode_blob(attributes.get(GCP_LLM_RESPONSE))
    if not isinstance(response, Mapping):
        return None
    content = response.get("content")
    if not isinstance(content, Mapping):
        return None
    return _text_only_parts(content.get("parts")).strip() or None


# ---------------------------------------------------------------------------
# Handoffs
# ---------------------------------------------------------------------------


def is_transfer_tool_span(attributes: Mapping[str, Any]) -> bool:
    """Return True for an ``execute_tool transfer_to_agent`` span.

    ``transfer_to_agent`` is ADK's ``sub_agents`` delegation primitive, not a
    domain tool, so the translator turns the span itself into
    ``ai.agent.handoff`` rather than adding an ``ai.tool.invoke`` row for it.
    """
    if attributes.get(GEN_AI_OPERATION_NAME) != OP_EXECUTE_TOOL:
        return False
    return attributes.get(GEN_AI_TOOL_NAME) == TRANSFER_TOOL_NAME


def transfer_target(attributes: Mapping[str, Any]) -> str:
    """Extract the destination agent from a ``transfer_to_agent`` span.

    The target lives in the tool's own arguments (``{"agent_name": "<target>"}``),
    which means it is unavailable when content capture is off -- the caller falls
    back to a plain tool span in that case, since a handoff with no destination
    draws no edge anyway.
    """
    args = _decode_blob(attributes.get(GCP_TOOL_CALL_ARGS))
    if not isinstance(args, Mapping):
        return ""
    target = args.get("agent_name")
    return target.strip() if isinstance(target, str) else ""


def translate_handoff_attributes(
    attributes: Mapping[str, Any],
    *,
    from_agent: str | None,
    to_agent: str,
) -> dict[str, Any]:
    """Build the attribute set for an ``ai.agent.handoff`` span.

    ``from_agent`` is optional: in adversarial cases the calling agent cannot be
    resolved, and we still emit the span with ``to`` set so the trace stays
    debuggable. The Graph View needs both ends to draw an edge.
    """
    translated = translate_attributes(attributes)
    translated[AIAttributes.OPERATION_TYPE] = AIAttributes.OPERATION_AGENT_HANDOFF
    if to_agent:
        translated[AIAttributes.AGENT_HANDOFF_TO] = to_agent
    if from_agent:
        translated[AIAttributes.AGENT_HANDOFF_FROM] = from_agent
    return translated


def agent_name(attributes: Mapping[str, Any], original_name: str | None) -> str:
    """Resolve an agent span's own name, preferring the attribute."""
    name = attributes.get(GEN_AI_AGENT_NAME)
    if isinstance(name, str) and name.strip():
        return name.strip()
    if original_name and " " in original_name:
        return original_name.split(" ", 1)[1].strip()
    return ""


def session_id(attributes: Mapping[str, Any]) -> str | None:
    """Return the ADK session id from whichever attribute carries it."""
    for key in (GEN_AI_CONVERSATION_ID, GCP_SESSION_ID):
        value = attributes.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def truthy_env(name: str, values: Iterable[str] = TRUTHY_ENV_VALUES) -> bool:
    """Return True when env var ``name`` is set to one of ``values``."""
    raw = os.getenv(name)
    if raw is None:
        return False
    return raw.strip().lower() in set(values)
