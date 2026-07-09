"""Pure-data translation tables for Haystack native OpenTelemetry spans.

Haystack emits spans with names like ``haystack.pipeline.run`` and
``haystack.component.run`` and attributes in the ``haystack.*`` namespace.
The Rhesis backend expects ``ai.*`` / ``function.*`` span names.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.integrations.tracing_helpers import (
    infer_model_provider,
    sanitize_for_tracing,
    truncate_content,
)
from rhesis.telemetry.schemas import AIOperationType

SPAN_PIPELINE_RUN = "haystack.pipeline.run"
SPAN_COMPONENT_RUN = "haystack.component.run"

TAG_PIPELINE_INPUT = "haystack.pipeline.input_data"
TAG_PIPELINE_OUTPUT = "haystack.pipeline.output_data"
TAG_PIPELINE_METADATA = "haystack.pipeline.metadata"
TAG_COMPONENT_NAME = "haystack.component.name"
TAG_COMPONENT_TYPE = "haystack.component.type"
TAG_COMPONENT_FQN = "haystack.component.fully_qualified_type"
TAG_COMPONENT_INPUT = "haystack.component.input"
TAG_COMPONENT_OUTPUT = "haystack.component.output"

HAYSTACK_SCOPE_PREFIXES = ("rhesis.sdk.haystack", "haystack")


def is_haystack_scope(scope_name: str | None) -> bool:
    """Return True if the OTEL instrumentation scope belongs to Haystack."""
    if not scope_name:
        return False
    return any(scope_name.startswith(prefix) for prefix in HAYSTACK_SCOPE_PREFIXES)


def is_haystack_span_name(name: str | None) -> bool:
    """Return True when the span name uses Haystack's native namespace."""
    return bool(name and name.startswith("haystack."))


def fallback_function_haystack_name(original_name: str) -> str:
    """Sanitize unknown Haystack span names into the ``function.haystack.*`` namespace."""
    if not original_name:
        return "function.haystack.unknown"
    sanitized = original_name.replace(" ", "_").replace(".", "_").lower()
    return f"function.haystack.{sanitized}"


def _classify_component(component_type: str, fqn: str) -> str:
    """Classify a Haystack component into a Rhesis operation kind."""
    haystack_type = component_type.lower()
    haystack_fqn = fqn.lower()

    if "handoff" in haystack_type or "handoff" in haystack_fqn:
        return "handoff"
    if "generator" in haystack_type or "llm" in haystack_type:
        return "llm"
    if "retriever" in haystack_type:
        return "retrieval"
    if "embedder" in haystack_type or "embedding" in haystack_type:
        return "embedding"
    if "tool" in haystack_type:
        return "tool"
    if "agent" in haystack_type:
        return "agent"
    if "ranker" in haystack_type or "reranker" in haystack_type:
        return "rerank"
    return "transform"


def _operation_to_span_name(kind: str, component_type: str) -> str:
    mapping = {
        "llm": AIOperationType.LLM_INVOKE,
        "retrieval": AIOperationType.RETRIEVAL,
        "embedding": AIOperationType.EMBEDDING_GENERATE,
        "tool": AIOperationType.TOOL_INVOKE,
        "agent": AIOperationType.AGENT_INVOKE,
        "handoff": AIOperationType.AGENT_HANDOFF,
        "rerank": AIOperationType.RERANK,
        "transform": AIOperationType.TRANSFORM,
    }
    if kind in mapping:
        return mapping[kind]
    safe_type = component_type.replace(" ", "_").lower() or "unknown"
    return f"function.haystack.component.{safe_type}"


def _operation_to_ai_type(kind: str) -> str:
    mapping = {
        "llm": AIAttributes.OPERATION_LLM_INVOKE,
        "retrieval": AIAttributes.OPERATION_RETRIEVAL,
        "embedding": AIAttributes.OPERATION_EMBEDDING_CREATE,
        "tool": AIAttributes.OPERATION_TOOL_INVOKE,
        "agent": AIAttributes.OPERATION_AGENT_INVOKE,
        "handoff": AIAttributes.OPERATION_AGENT_HANDOFF,
        "rerank": AIAttributes.OPERATION_RERANK,
        "transform": AIAttributes.OPERATION_TRANSFORM,
    }
    return mapping.get(kind, AIAttributes.OPERATION_TRANSFORM)


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return value
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value
    return value


def _extract_messages(payload: Any, *, key: str | None = None) -> list[dict[str, Any]]:
    payload = _parse_jsonish(payload)
    if payload is None:
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        if key and key in payload:
            nested = payload[key]
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        for candidate in ("messages", "replies", "prompt", "documents"):
            nested = payload.get(candidate)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _message_role(message: dict[str, Any]) -> str | None:
    role = message.get("role") or message.get("_role")
    if isinstance(role, str):
        return role
    return None


def _message_content(message: dict[str, Any]) -> str | None:
    for key in ("content", "text", "answer"):
        value = message.get(key)
        if value is not None:
            return truncate_content(sanitize_for_tracing(value))
    return None


def _extract_usage(payload: Any) -> dict[str, Any] | None:
    payload = _parse_jsonish(payload)
    if not isinstance(payload, dict):
        return None

    for container_key in ("replies", "messages", "meta"):
        container = payload.get(container_key)
        if isinstance(container, list):
            for item in container:
                if isinstance(item, dict):
                    usage = (item.get("meta") or {}).get("usage")
                    if isinstance(usage, dict):
                        return usage
        elif isinstance(container, dict):
            usage = container.get("usage")
            if isinstance(usage, dict):
                return usage

    usage = payload.get("usage")
    if isinstance(usage, dict):
        return usage
    return None


def _extract_model(payload: Any, attributes: Mapping[str, Any]) -> str | None:
    payload = _parse_jsonish(payload)
    if isinstance(payload, dict):
        for container_key in ("replies", "messages"):
            container = payload.get(container_key)
            if isinstance(container, list):
                for item in container:
                    if isinstance(item, dict):
                        meta = item.get("meta") or {}
                        model = meta.get("model")
                        if isinstance(model, str) and model:
                            return model

    metadata = _parse_jsonish(attributes.get(TAG_PIPELINE_METADATA))
    if isinstance(metadata, dict):
        model = metadata.get("model")
        if isinstance(model, str) and model:
            return model
    return None


def _infer_provider_from_fqn(fqn: str) -> str | None:
    lowered = fqn.lower()
    if "openai" in lowered:
        return "openai"
    if "anthropic" in lowered:
        return "anthropic"
    if "google" in lowered or "gemini" in lowered:
        return "google"
    if "cohere" in lowered:
        return "cohere"
    if "huggingface" in lowered:
        return "huggingface"
    return None


def translate_span_name(original_name: str, attributes: Mapping[str, Any]) -> str:
    """Translate a Haystack span name to the Rhesis ``ai.*`` / ``function.*`` schema."""
    if original_name == SPAN_PIPELINE_RUN:
        return AIOperationType.AGENT_INVOKE

    if original_name == SPAN_COMPONENT_RUN or original_name.startswith("haystack.component."):
        component_type = str(attributes.get(TAG_COMPONENT_TYPE, ""))
        fqn = str(attributes.get(TAG_COMPONENT_FQN, ""))
        kind = _classify_component(component_type, fqn)
        return _operation_to_span_name(kind, component_type)

    if is_haystack_span_name(original_name):
        return fallback_function_haystack_name(original_name)

    return original_name


def translate_attributes(attributes: Mapping[str, Any], *, span_name: str) -> dict[str, Any]:
    """Build translated attributes for a Haystack span."""
    translated: dict[str, Any] = dict(attributes)
    translated.setdefault(AIAttributes.SYSTEM, "haystack")

    if span_name == SPAN_PIPELINE_RUN or attributes.get(TAG_PIPELINE_INPUT) is not None:
        metadata = _parse_jsonish(attributes.get(TAG_PIPELINE_METADATA))
        agent_name = "haystack_pipeline"
        if isinstance(metadata, dict) and metadata.get("name"):
            agent_name = str(metadata["name"])
        translated.setdefault(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
        translated.setdefault(AIAttributes.AGENT_NAME, agent_name)
        return translated

    component_type = str(attributes.get(TAG_COMPONENT_TYPE, ""))
    fqn = str(attributes.get(TAG_COMPONENT_FQN, ""))
    component_name = attributes.get(TAG_COMPONENT_NAME)
    kind = _classify_component(component_type, fqn)

    translated.setdefault(AIAttributes.OPERATION_TYPE, _operation_to_ai_type(kind))
    if component_name:
        translated.setdefault(AIAttributes.AGENT_NAME, str(component_name))

    if kind == "tool":
        translated.setdefault(AIAttributes.TOOL_NAME, str(component_name or component_type))
        translated.setdefault(AIAttributes.TOOL_TYPE, "function")

    model = _extract_model(attributes.get(TAG_COMPONENT_OUTPUT), attributes)
    if model:
        translated.setdefault(AIAttributes.MODEL_NAME, model)
        provider = infer_model_provider(model) or _infer_provider_from_fqn(fqn)
        if provider:
            translated.setdefault(AIAttributes.MODEL_PROVIDER, provider)

    usage = _extract_usage(attributes.get(TAG_COMPONENT_OUTPUT))
    if usage:
        # Reuse helper logic via a lightweight stand-in span dict update path.
        token_attrs: dict[str, Any] = {}
        from rhesis.sdk.telemetry.utils.token_extraction import extract_token_usage

        prompt, completion, total = extract_token_usage(usage)
        if prompt:
            token_attrs[AIAttributes.LLM_TOKENS_INPUT] = prompt
        if completion:
            token_attrs[AIAttributes.LLM_TOKENS_OUTPUT] = completion
        if total:
            token_attrs[AIAttributes.LLM_TOKENS_TOTAL] = total
        translated.update({k: v for k, v in token_attrs.items() if k not in translated})

    return translated


def synthesize_events(
    attributes: Mapping[str, Any],
    *,
    span_name: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Build Rhesis span events from Haystack content tags."""
    events: list[tuple[str, dict[str, Any]]] = []

    if span_name == SPAN_PIPELINE_RUN:
        pipeline_input = attributes.get(TAG_PIPELINE_INPUT)
        pipeline_output = attributes.get(TAG_PIPELINE_OUTPUT)
        if pipeline_input is not None:
            events.append(
                (
                    AIEvents.AGENT_INPUT,
                    {
                        AIAttributes.AGENT_INPUT_CONTENT: truncate_content(
                            sanitize_for_tracing(pipeline_input)
                        )
                    },
                )
            )
        if pipeline_output is not None:
            events.append(
                (
                    AIEvents.AGENT_OUTPUT,
                    {
                        AIAttributes.AGENT_OUTPUT_CONTENT: truncate_content(
                            sanitize_for_tracing(pipeline_output)
                        )
                    },
                )
            )
        return events

    component_type = str(attributes.get(TAG_COMPONENT_TYPE, ""))
    fqn = str(attributes.get(TAG_COMPONENT_FQN, ""))
    kind = _classify_component(component_type, fqn)
    component_input = attributes.get(TAG_COMPONENT_INPUT)
    component_output = attributes.get(TAG_COMPONENT_OUTPUT)

    if kind == "llm":
        for message in _extract_messages(component_input):
            content = _message_content(message)
            if content is None:
                continue
            role = _message_role(message) or "user"
            events.append(
                (
                    AIEvents.PROMPT,
                    {AIAttributes.PROMPT_ROLE: role, AIAttributes.PROMPT_CONTENT: content},
                )
            )
        for message in _extract_messages(component_output, key="replies"):
            content = _message_content(message)
            if content is not None:
                events.append((AIEvents.COMPLETION, {AIAttributes.COMPLETION_CONTENT: content}))
        return events

    if kind == "retrieval":
        if component_input is not None:
            events.append(
                (
                    AIEvents.RETRIEVAL_QUERY,
                    {"ai.retrieval.query": truncate_content(sanitize_for_tracing(component_input))},
                )
            )
        if component_output is not None:
            events.append(
                (
                    AIEvents.RETRIEVAL_RESULTS,
                    {
                        "ai.retrieval.results": truncate_content(
                            sanitize_for_tracing(component_output)
                        )
                    },
                )
            )
        return events

    if kind == "tool":
        if component_input is not None:
            events.append(
                (
                    AIEvents.TOOL_INPUT,
                    {AIAttributes.TOOL_INPUT_CONTENT: truncate_content(sanitize_for_tracing(component_input))},
                )
            )
        if component_output is not None:
            events.append(
                (
                    AIEvents.TOOL_OUTPUT,
                    {
                        AIAttributes.TOOL_OUTPUT_CONTENT: truncate_content(
                            sanitize_for_tracing(component_output)
                        )
                    },
                )
            )
        return events

    if kind in {"agent", "handoff"}:
        if component_input is not None:
            events.append(
                (
                    AIEvents.AGENT_INPUT,
                    {AIAttributes.AGENT_INPUT_CONTENT: truncate_content(sanitize_for_tracing(component_input))},
                )
            )
        if component_output is not None:
            events.append(
                (
                    AIEvents.AGENT_OUTPUT,
                    {
                        AIAttributes.AGENT_OUTPUT_CONTENT: truncate_content(
                            sanitize_for_tracing(component_output)
                        )
                    },
                )
            )
    return events
