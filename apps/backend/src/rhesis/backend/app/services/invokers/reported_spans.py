"""Spans for what an endpoint reported in its response, for endpoints that send no traces.

A REST or WebSocket endpoint leaves one span, the invocation. When its response mapping
exposes ``tool_calls`` or ``context``, those become child spans of that invocation: one
``tool.invoke`` span per tool call, one ``retrieval`` span for the context. Metrics can then
target tool calls and retrievals on endpoints that report them but are not instrumented.

They carry ``rhesis.span.source = "reported"``: they come from the endpoint's own account, so
they have no timing of their own and stand in for spans the endpoint did not send.
"""

import json
import secrets
from datetime import timedelta
from typing import Any, Dict, List, Optional

from rhesis.telemetry.schemas import OTELSpan, SpanEvent

SOURCE_ATTRIBUTE = "rhesis.span.source"
REPORTED = "reported"


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


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
    # Spans are ordered by start time; a microsecond apart keeps the reported order.
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
        end_time=max(start, parent.end_time),
        attributes={SOURCE_ATTRIBUTE: REPORTED, **attributes},
        events=[
            SpanEvent(name=event, timestamp=max(start, parent.end_time), attributes={key: value})
            for event, key, value in events
            if value is not None
        ],
    )


def reported_spans(result: Optional[Dict[str, Any]], parent: OTELSpan) -> List[OTELSpan]:
    """Child spans for the tool calls and context an endpoint's mapped response reported."""
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
                {"ai.operation.type": "tool.invoke", "ai.tool.name": fields["name"]},
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
                {"ai.operation.type": "retrieval"},
                [("ai.retrieval.results", "ai.completion.content", _text(context))],
            )
        )
    return spans
