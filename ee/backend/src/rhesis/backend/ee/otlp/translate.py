"""Translate decoded OTLP spans into Rhesis ``OTELSpan``s.

The GenAI mapping itself is shared with the SDK (:mod:`rhesis.telemetry.genai`);
this module handles the OTLP side: AnyValue, ids, timestamps, kinds, status,
resource and scope, and per-span validation for ``partial_success``.
"""

import base64
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import Span, Status
from pydantic import ValidationError

from rhesis.telemetry import genai
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import OTELSpan, SpanEvent, SpanKind, SpanLink, StatusCode

# Resource attributes that scope a span. The project attribute is a Rhesis
# extension; the environment one is the OTel standard (and its older name).
RESOURCE_PROJECT_ID = "rhesis.project_id"
RESOURCE_ENVIRONMENT = ("deployment.environment.name", "deployment.environment")
DEFAULT_ENVIRONMENT = "development"

# Standard names for the instrumentation scope outside OTLP (OTel "otel.scope.*").
SCOPE_NAME = "otel.scope.name"
SCOPE_VERSION = "otel.scope.version"

# Marks spans that arrived over OTLP, so they can be told apart from SDK spans.
INGEST_SOURCE = "rhesis.ingest.source"
INGEST_SOURCE_OTLP = "otlp"

logger = logging.getLogger(__name__)

_MAX_CONVERSATION_ID = 255
_MAX_ENVIRONMENT = 50

_SPAN_KINDS = {
    Span.SPAN_KIND_UNSPECIFIED: SpanKind.INTERNAL,
    Span.SPAN_KIND_INTERNAL: SpanKind.INTERNAL,
    Span.SPAN_KIND_SERVER: SpanKind.SERVER,
    Span.SPAN_KIND_CLIENT: SpanKind.CLIENT,
    Span.SPAN_KIND_PRODUCER: SpanKind.PRODUCER,
    Span.SPAN_KIND_CONSUMER: SpanKind.CONSUMER,
}

_STATUS_CODES = {
    Status.STATUS_CODE_UNSET: StatusCode.UNSET,
    Status.STATUS_CODE_OK: StatusCode.OK,
    Status.STATUS_CODE_ERROR: StatusCode.ERROR,
}


@dataclass
class TranslatedRequest:
    spans: List[OTELSpan] = field(default_factory=list)
    rejected: int = 0
    errors: List[str] = field(default_factory=list)

    def reject(self, message: str) -> None:
        self.rejected += 1
        # Only the first few reach the response; one bad exporter can send thousands.
        if len(self.errors) < 5:
            self.errors.append(message)


# ---------------------------------------------------------------------------
# AnyValue
# ---------------------------------------------------------------------------


def any_value_to_python(value: AnyValue) -> Any:
    """AnyValue as plain Python: lists for arrays, dicts for kvlists."""
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    if kind == "array_value":
        return [any_value_to_python(v) for v in value.array_value.values]
    if kind == "kvlist_value":
        return {kv.key: any_value_to_python(kv.value) for kv in value.kvlist_value.values}
    if kind == "bytes_value":
        return base64.b64encode(value.bytes_value).decode("ascii")
    return getattr(value, kind)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, bool, int, float))


def attribute_value(value: AnyValue) -> Any:
    """An attribute value in the shape SDK-sent spans have.

    The OTel SDK only allows scalars and arrays of scalars on attributes, so
    that is what the rest of Rhesis expects. Anything richer (a kvlist, or an
    array holding one, like structured ``gen_ai.input.messages``) is stored as a
    JSON string, which the GenAI helpers parse back.
    """
    python = any_value_to_python(value)
    if _is_scalar(python):
        return python
    if isinstance(python, list) and all(_is_scalar(v) for v in python):
        return python
    return json.dumps(python, ensure_ascii=False, default=str)


def attributes_to_dict(attributes: List[KeyValue]) -> Dict[str, Any]:
    return {kv.key: attribute_value(kv.value) for kv in attributes}


# ---------------------------------------------------------------------------
# Ids and time
# ---------------------------------------------------------------------------


def _hex_id(raw: bytes, size: int, name: str) -> str:
    if len(raw) != size or not any(raw):
        raise ValueError(f"invalid {name} ({len(raw)} bytes)")
    return raw.hex()


def _nanos_to_datetime(nanos: int) -> datetime:
    return datetime.fromtimestamp(nanos / 1_000_000_000, tz=timezone.utc)


# ---------------------------------------------------------------------------
# Spans
# ---------------------------------------------------------------------------


def _resource_environment(resource: Mapping[str, Any]) -> str:
    for key in RESOURCE_ENVIRONMENT:
        value = resource.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:_MAX_ENVIRONMENT]
    return DEFAULT_ENVIRONMENT


def _events(span: Span, start_time: datetime) -> tuple[List[SpanEvent], Optional[str]]:
    """Original events (legacy message names translated) and the first exception message."""
    events: List[SpanEvent] = []
    exception: Optional[str] = None
    for event in span.events:
        attrs = attributes_to_dict(event.attributes)
        if exception is None and genai.is_exception_event(event.name):
            exception = genai.exception_message(attrs)
        events.append(
            SpanEvent(
                name=genai.translate_event_name(event.name),
                timestamp=(
                    _nanos_to_datetime(event.time_unix_nano) if event.time_unix_nano else start_time
                ),
                attributes=genai.translate_event_attributes(event.name, attrs),
            )
        )
    return events, exception


def _synthesized_events(attributes: Mapping[str, Any], at: datetime) -> List[SpanEvent]:
    synthesized = [
        *genai.synthesize_message_events(attributes, chat_operations=genai.INFERENCE_OPERATIONS),
        *genai.synthesize_agent_io_events(attributes),
        *genai.synthesize_tool_io_events(attributes),
    ]
    return [SpanEvent(name=name, timestamp=at, attributes=attrs) for name, attrs in synthesized]


def _status(
    span: Span, attributes: Mapping[str, Any], exception: Optional[str]
) -> tuple[StatusCode, Optional[str]]:
    code = _STATUS_CODES.get(span.status.code, StatusCode.UNSET)
    message = span.status.message or None
    error_type = attributes.get("error.type")
    # error.type is how the GenAI conventions mark a failed operation; an
    # instrumentation that sets it without the span status still failed.
    if code is StatusCode.UNSET and (error_type or exception):
        code = StatusCode.ERROR
    if code is StatusCode.ERROR and not message:
        message = exception or (str(error_type) if error_type else None)
    return code, message


def translate_span(
    span: Span,
    resource: Mapping[str, Any],
    scope_name: str,
    scope_version: str,
) -> OTELSpan:
    """One OTLP span as a Rhesis span. Raises ``ValueError``/``ValidationError``."""
    trace_id = _hex_id(span.trace_id, 16, "trace_id")
    span_id = _hex_id(span.span_id, 8, "span_id")
    parent_span_id = (
        _hex_id(span.parent_span_id, 8, "parent_span_id") if span.parent_span_id else None
    )

    raw = attributes_to_dict(span.attributes)
    span_name, operation_type = genai.classify_span(span.name, raw)
    attributes = genai.translate_attributes(raw)
    if operation_type:
        # The classifier sees more than the operation name (a transfer is an
        # execute_tool that hands off), so it wins over the plain rename.
        attributes[AIAttributes.OPERATION_TYPE] = operation_type
    attributes.setdefault(AIAttributes.FUNCTION_NAME, span.name)
    attributes[INGEST_SOURCE] = INGEST_SOURCE_OTLP
    if scope_name:
        attributes.setdefault(SCOPE_NAME, scope_name)
    if scope_version:
        attributes.setdefault(SCOPE_VERSION, scope_version)

    start_time = _nanos_to_datetime(span.start_time_unix_nano)
    end_time = _nanos_to_datetime(span.end_time_unix_nano)
    events, exception = _events(span, start_time)
    events.extend(_synthesized_events(raw, end_time))
    status_code, status_message = _status(span, raw, exception)

    conversation_id = raw.get(genai.GEN_AI_CONVERSATION_ID)
    return OTELSpan(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        project_id=resource.get(RESOURCE_PROJECT_ID) or None,
        environment=_resource_environment(resource),
        conversation_id=(str(conversation_id)[:_MAX_CONVERSATION_ID] if conversation_id else None),
        span_name=span_name,
        span_kind=_SPAN_KINDS.get(span.kind, SpanKind.INTERNAL),
        start_time=start_time,
        end_time=max(end_time, start_time),
        status_code=status_code,
        status_message=status_message,
        attributes=attributes,
        events=events,
        links=[
            SpanLink(
                trace_id=_hex_id(link.trace_id, 16, "link trace_id"),
                span_id=_hex_id(link.span_id, 8, "link span_id"),
                attributes=attributes_to_dict(link.attributes),
            )
            for link in span.links
        ],
        resource=dict(resource),
    )


def _descendants(root: OTELSpan, children: Dict[tuple[str, str], List[OTELSpan]]) -> List[OTELSpan]:
    found: List[OTELSpan] = []
    seen = {root.span_id}
    stack = list(children.get((root.trace_id, root.span_id), ()))
    while stack:
        span = stack.pop()
        if span.span_id in seen:
            continue  # a parent loop
        seen.add(span.span_id)
        found.append(span)
        stack.extend(children.get((span.trace_id, span.span_id), ()))
    return found


def _first(spans: List[OTELSpan], read: Callable[[Mapping[str, Any]], Optional[str]]):
    return next((text for span in spans if (text := read(span.attributes))), None)


def _turn_io(root: OTELSpan, below: List[OTELSpan]) -> tuple[Optional[str], Optional[str]]:
    """The turn's input and output: the root's, else its agents', else its model calls'.

    Input comes from the earliest span that has it and output from the latest,
    so a handoff turn gets the first agent's question and the last agent's answer.
    """

    def operation(span: OTELSpan) -> Any:
        return span.attributes.get(genai.GEN_AI_OPERATION_NAME)

    agents = [s for s in below if genai.is_invoke_operation(operation(s))]
    models = [
        s
        for s in below
        if isinstance(operation(s), str) and operation(s) in genai.INFERENCE_OPERATIONS
    ]
    by_start = [
        root,
        *sorted(agents, key=lambda s: s.start_time),
        *sorted(models, key=lambda s: s.start_time),
    ]
    by_end = [root] + [
        *sorted(agents, key=lambda s: s.end_time, reverse=True),
        *sorted(models, key=lambda s: s.end_time, reverse=True),
    ]
    return _first(by_start, genai.agent_turn_input), _first(by_end, genai.agent_turn_output)


def _outermost_agent(root: OTELSpan, below: List[OTELSpan]) -> Optional[OTELSpan]:
    by_id = {s.span_id: s for s in below}

    def depth(span: OTELSpan) -> int:
        count, current, seen = 0, span, {span.span_id}
        while current.parent_span_id in by_id and current.parent_span_id not in seen:
            seen.add(current.parent_span_id)
            current, count = by_id[current.parent_span_id], count + 1
        return count

    agents = [
        s for s in below if genai.is_invoke_operation(s.attributes.get(genai.GEN_AI_OPERATION_NAME))
    ]
    return min(agents, key=lambda s: (depth(s), s.start_time), default=None)


def _stamp_turns(spans: List[OTELSpan]) -> None:
    """Give each root span the turn's input, output, agent and conversation.

    The root is what the trace list, conversation view and evaluator read, but
    the turn text often sits below it: an agent inside an HTTP server span, a
    framework that records messages only on its model calls, or a handoff
    between agents. Only spans in the same request are seen.
    """
    children: Dict[tuple[str, str], List[OTELSpan]] = defaultdict(list)
    for span in spans:
        if span.parent_span_id is not None:
            children[(span.trace_id, span.parent_span_id)].append(span)

    for root in spans:
        if root.parent_span_id is not None:
            continue
        below = _descendants(root, children)
        turn_input, turn_output = _turn_io(root, below)
        if turn_input:
            root.attributes.setdefault(genai.CONVERSATION_INPUT, turn_input)
        if turn_output:
            root.attributes.setdefault(genai.CONVERSATION_OUTPUT, turn_output)
        agent = _outermost_agent(root, below)
        if agent is None:
            continue
        # The trace list's Agent column reads the root.
        agent_name = agent.attributes.get(AIAttributes.AGENT_NAME)
        if agent_name:
            root.attributes.setdefault(AIAttributes.AGENT_NAME, agent_name)
        if root.conversation_id is None and agent.conversation_id:
            root.conversation_id = agent.conversation_id


def _link_handoffs(spans: List[OTELSpan]) -> None:
    """Name the agent handing off on each transfer span: its nearest invoke_* ancestor.

    The conventions record only the target; the span graph draws an edge from
    ``ai.agent.handoff.from`` to ``ai.agent.handoff.to``. Ancestors exported in
    an earlier request are not seen.
    """
    by_id = {(s.trace_id, s.span_id): s for s in spans}
    for span in spans:
        attributes = span.attributes
        if attributes.get(AIAttributes.OPERATION_TYPE) != AIAttributes.OPERATION_AGENT_HANDOFF:
            continue
        if AIAttributes.AGENT_HANDOFF_FROM in attributes:
            continue
        seen = {span.span_id}
        parent = by_id.get((span.trace_id, span.parent_span_id or ""))
        while parent is not None and parent.span_id not in seen:
            seen.add(parent.span_id)
            name = parent.attributes.get(AIAttributes.AGENT_NAME)
            if name and genai.is_invoke_operation(
                parent.attributes.get(genai.GEN_AI_OPERATION_NAME)
            ):
                attributes[AIAttributes.AGENT_HANDOFF_FROM] = name
                break
            parent = by_id.get((parent.trace_id, parent.parent_span_id or ""))


def translate_request(request: ExportTraceServiceRequest) -> TranslatedRequest:
    """Translate every span; invalid ones are counted for ``partial_success``."""
    result = TranslatedRequest()
    for resource_spans in request.resource_spans:
        resource = attributes_to_dict(resource_spans.resource.attributes)
        for scope_spans in resource_spans.scope_spans:
            scope = scope_spans.scope
            for span in scope_spans.spans:
                try:
                    result.spans.append(translate_span(span, resource, scope.name, scope.version))
                except (ValueError, ValidationError) as exc:
                    name = span.name or "<unnamed>"
                    result.reject(f"span {name!r}: {str(exc).splitlines()[0]}")
                except Exception as exc:
                    # One odd span must not fail the batch with a 500, which
                    # exporters do not retry.
                    logger.warning("Rejected OTLP span %r: %r", span.name, exc, exc_info=True)
                    result.reject(f"span {span.name or '<unnamed>'!r}: could not be translated")
    _stamp_turns(result.spans)
    _link_handoffs(result.spans)
    return result
