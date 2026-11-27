"""What an endpoint reported in its response, for endpoints that send no traces.

A REST or WebSocket endpoint leaves one span, the invocation. The response mapping is a
mapping onto that trace, and every field it can map has one place in it:

- ``tool_calls``: one ``tool.invoke`` child span per call;
- ``context``: one ``retrieval`` child span;
- ``usage``: one ``llm.invoke`` child span holding the token counts, so trace totals count them;
- ``metadata``: one attribute per key on the invocation span (``rhesis.reported.metadata.<key>``);
- any other mapped field: an attribute on the invocation span (``rhesis.reported.<name>``).

Child spans carry ``rhesis.span.source = "reported"``. They come from the endpoint's own
account, so they have no timing of their own: each starts and ends at the same instant.
"""

import json
import secrets
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import OTELSpan, SpanEvent

SOURCE_ATTRIBUTE = "rhesis.span.source"
REPORTED = "reported"

REPORTED_ATTRIBUTE_PREFIX = "rhesis.reported."
REPORTED_METADATA_PREFIX = "rhesis.reported.metadata."
# A long value is cut on its own, so one large key never costs the others.
MAX_REPORTED_VALUE_LENGTH = 2000

_USAGE_KEYS = {
    AIAttributes.LLM_TOKENS_INPUT: ("input_tokens", "prompt_tokens", "input"),
    AIAttributes.LLM_TOKENS_OUTPUT: ("output_tokens", "completion_tokens", "output"),
    AIAttributes.LLM_TOKENS_TOTAL: ("total_tokens", "total"),
}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


def _attribute_value(value: Any) -> Any:
    """A span attribute for a reported value: numbers and booleans as they are, so rules can
    compare them, and anything else as text."""
    if isinstance(value, (bool, int, float)):
        return value
    return _text(value)[:MAX_REPORTED_VALUE_LENGTH]


def _parsed(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def reported_attributes(
    result: Optional[Dict[str, Any]], fields: Iterable[str] = ()
) -> Dict[str, Any]:
    """Attributes for the invocation span: each ``metadata`` key on its own, and each of
    ``fields`` (other mapped response fields) that the response set."""
    if not isinstance(result, dict):
        return {}
    attributes: Dict[str, Any] = {}
    metadata = _parsed(result.get("metadata"))
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if value is not None:
                attributes[f"{REPORTED_METADATA_PREFIX}{key}"] = _attribute_value(value)
    for name in fields:
        value = result.get(name)
        if value is not None:
            attributes[f"{REPORTED_ATTRIBUTE_PREFIX}{name}"] = _attribute_value(value)
    return attributes


def _token_counts(usage: Any) -> Dict[str, int]:
    """Token counts from a reported usage object, in OpenAI's or Anthropic's shape."""
    usage = _parsed(usage)
    if not isinstance(usage, dict):
        return {}
    counts: Dict[str, int] = {}
    for attribute, keys in _USAGE_KEYS.items():
        value = next((usage[k] for k in keys if k in usage), None)
        if isinstance(value, int) and not isinstance(value, bool):
            counts[attribute] = value
    return counts


def _tool_call_fields(call: Any) -> Dict[str, Any]:
    """Name, arguments and result of one reported tool call.

    Responses use either a flat shape (``name``/``arguments``) or OpenAI's
    (``function: {name, arguments}``); the result, when reported, sits beside them.
    """
    if not isinstance(call, dict):
        return {"name": _text(call), "arguments": None, "output": None}
    function = call.get("function") if isinstance(call.get("function"), dict) else {}
    name = call.get("name") or call.get("tool") or function.get("name") or "tool"
    arguments = _first_set([call, function], ("arguments", "args", "input"))
    output = _first_set([call], ("output", "result", "content"))
    return {"name": str(name), "arguments": arguments, "output": output}


def _first_set(sources: List[Dict[str, Any]], keys: tuple) -> Any:
    # A key present but null (``"arguments": null`` beside ``function.arguments``) is skipped.
    return next(
        (s[k] for s in sources for k in keys if s.get(k) not in (None, "")),
        None,
    )


def _child(parent: OTELSpan, index: int, name: str, attributes: Dict[str, Any], events) -> OTELSpan:
    # Spans are ordered by start time; a microsecond apart keeps the reported order. Start and
    # end are the same instant: the endpoint reported what happened, not when.
    start = parent.start_time + timedelta(microseconds=index)
    return OTELSpan(
        trace_id=parent.trace_id,
        span_id=secrets.token_hex(8),
        parent_span_id=parent.span_id,
        project_id=parent.project_id,
        environment=parent.environment,
        conversation_id=parent.conversation_id,
        span_name=name,
        start_time=start,
        end_time=start,
        attributes={SOURCE_ATTRIBUTE: REPORTED, **attributes},
        events=[
            SpanEvent(name=event, timestamp=start, attributes={key: value})
            for event, key, value in events
            if value is not None
        ],
    )


def reported_spans(result: Optional[Dict[str, Any]], parent: OTELSpan) -> List[OTELSpan]:
    """Child spans for the tool calls, context and usage an endpoint's mapped response
    reported."""
    if not isinstance(result, dict):
        return []

    spans: List[OTELSpan] = []
    tool_calls = result.get("tool_calls")
    for call in tool_calls if isinstance(tool_calls, list) else []:
        fields = _tool_call_fields(call)
        spans.append(
            _child(
                parent,
                len(spans),
                "ai.tool.invoke",
                {
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
                    AIAttributes.TOOL_NAME: fields["name"],
                },
                [
                    (
                        "ai.tool.input",
                        "ai.tool.input",
                        None if fields["arguments"] is None else _text(fields["arguments"]),
                    ),
                    (
                        "ai.tool.output",
                        "ai.tool.output",
                        None if fields["output"] is None else _text(fields["output"]),
                    ),
                ],
            )
        )

    context = result.get("context")
    if context:
        spans.append(
            _child(
                parent,
                len(spans),
                "ai.retrieval",
                {AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RETRIEVAL},
                [("ai.retrieval.results", "ai.completion.content", _text(context))],
            )
        )

    tokens = _token_counts(result.get("usage"))
    if tokens:
        spans.append(
            _child(
                parent,
                len(spans),
                "ai.llm.invoke",
                {AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE, **tokens},
                [],
            )
        )
    return spans
