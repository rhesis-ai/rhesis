"""Traces built in memory from a response or a conversation, for evaluating with nothing stored.

They have the shape a stored REST invocation has: one invocation span per turn, carrying the
turn's input, output and metadata, with the reported tool calls and context as child spans.
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union

from rhesis.sdk.entities.trace import (
    FROM_CONVERSATION,
    FROM_RESPONSE,
    RESPONSE_METADATA_ATTRIBUTE,
    TRACE_SOURCE_ATTRIBUTE,
    Span,
    Trace,
)
from rhesis.sdk.telemetry.reported_spans import reported_spans
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.schemas import OTELSpan

if TYPE_CHECKING:
    from rhesis.sdk.metrics.conversational.types import ConversationHistory

INVOCATION_SPAN_NAME = "function.endpoint_invoke"

_CONVERSATION = ConversationContext.SpanAttributes


def span_from_otel(span: OTELSpan) -> Span:
    """An SDK span from an OpenTelemetry one, without children."""
    return Span(
        span_id=span.span_id,
        span_name=span.span_name,
        span_kind=span.span_kind.value,
        start_time=span.start_time,
        end_time=span.end_time,
        duration_ms=(span.end_time - span.start_time).total_seconds() * 1000,
        status_code=span.status_code.value,
        status_message=span.status_message,
        attributes=dict(span.attributes),
        events=[event.model_dump() for event in span.events],
    )


def _turn(
    trace_id: str,
    start: datetime,
    source: str,
    input: Any,
    output: Any,
    context: Any = None,
    tool_calls: Any = None,
    metadata: Any = None,
    conversation_id: Optional[str] = None,
) -> Span:
    attributes: Dict[str, Any] = {TRACE_SOURCE_ATTRIBUTE: source}
    if input not in (None, ""):
        attributes[_CONVERSATION.CONVERSATION_INPUT] = _text(input)
    if output not in (None, ""):
        attributes[_CONVERSATION.CONVERSATION_OUTPUT] = _text(output)
    if metadata:
        attributes[RESPONSE_METADATA_ATTRIBUTE] = json.dumps(metadata, default=str)
    if conversation_id:
        attributes[_CONVERSATION.CONVERSATION_ID] = conversation_id
    invocation = OTELSpan(
        trace_id=trace_id,
        span_id=secrets.token_hex(8),
        conversation_id=conversation_id,
        span_name=INVOCATION_SPAN_NAME,
        start_time=start,
        end_time=start,
        attributes=attributes,
    )
    root = span_from_otel(invocation)
    reported = reported_spans({"tool_calls": tool_calls, "context": context}, invocation)
    root.children = [span_from_otel(span) for span in reported]
    return root


def _in_memory(trace: Trace) -> Trace:
    # Its spans are all there is: reading it must never fetch it from the API by its trace_id.
    trace._detail_loaded = True
    return trace


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


def trace_from_response(
    input: Any,
    output: Any,
    *,
    context: Any = None,
    tool_calls: Any = None,
    metadata: Any = None,
) -> Trace:
    """A trace of one request and its response."""
    trace_id = secrets.token_hex(16)
    root = _turn(
        trace_id,
        datetime.now(timezone.utc),
        FROM_RESPONSE,
        input,
        output,
        context=context,
        tool_calls=tool_calls,
        metadata=metadata,
    )
    return _in_memory(Trace(trace_id=trace_id, root_spans=[root]))


def _message(message: Any) -> Dict[str, Any]:
    if isinstance(message, dict):
        return message
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    raise TypeError(
        "conversation must be a ConversationHistory or a list of messages, "
        f"not one holding {type(message).__name__}"
    )


def _turns(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pair each user message with the assistant reply after it. A reply with no user
    message before it is a turn of its own; system and tool messages are not turns."""
    turns: List[Dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role == "user":
            turns.append({"input": message.get("content")})
        elif role == "assistant":
            if not turns or "reply" in turns[-1]:
                turns.append({})
            turns[-1]["reply"] = message
    return turns


def trace_from_conversation(
    conversation: Union["ConversationHistory", Sequence[Any]],
    *,
    conversation_id: Optional[str] = None,
) -> Trace:
    """A trace of a conversation: one invocation span per turn, in order, each with the
    tool calls, context and metadata its reply reported."""
    messages = getattr(conversation, "messages", conversation)
    if isinstance(messages, (str, bytes, dict)):
        raise TypeError(
            "conversation must be a ConversationHistory or a list of messages, "
            f"not {type(messages).__name__}"
        )
    conversation_id = (
        conversation_id or getattr(conversation, "conversation_id", None) or secrets.token_hex(8)
    )
    trace_id = secrets.token_hex(16)
    start = datetime.now(timezone.utc)
    roots = []
    for index, turn in enumerate(_turns([_message(m) for m in messages])):
        reply = turn.get("reply") or {}
        roots.append(
            _turn(
                trace_id,
                # A millisecond apart, so the turns keep their order however they are sorted.
                start + timedelta(milliseconds=index),
                FROM_CONVERSATION,
                turn.get("input"),
                reply.get("content"),
                context=reply.get("context"),
                tool_calls=reply.get("tool_calls"),
                metadata=reply.get("metadata"),
                conversation_id=conversation_id,
            )
        )
    return _in_memory(Trace(trace_id=trace_id, conversation_id=conversation_id, root_spans=roots))
