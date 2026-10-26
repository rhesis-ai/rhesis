"""The trace a metric reads when it declares ``trace``.

Built as the SDK's ``Trace`` with its span tree loaded, the same shape the trace detail route
returns, so a metric sees what a user sees through the API. Annotations, costs and tags are
left out: no metric reads them, and loading them costs a query per span.
"""

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.schemas import OTELSpan

from rhesis.backend.app.crud.telemetry import get_trace_by_id
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.services.invokers.tracing import EndpointAttributes
from rhesis.backend.app.services.telemetry.span_types import classify_span_type
from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.telemetry.reported_spans import reported_spans

logger = logging.getLogger(__name__)

ConversationAttributes = ConversationContext.SpanAttributes


def _node(
    *,
    row_id: Optional[str],
    span_id: str,
    parent_span_id: Optional[str],
    span_name: str,
    span_kind: str,
    span_type: Optional[str],
    start_time: datetime,
    end_time: datetime,
    status_code: str,
    status_message: Optional[str],
    attributes: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "id": row_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "span_name": span_name,
        "span_kind": span_kind,
        "span_type": span_type or classify_span_type(attributes),
        "start_time": start_time,
        "end_time": end_time,
        "duration_ms": (end_time - start_time).total_seconds() * 1000,
        "status_code": status_code,
        "status_message": status_message,
        "attributes": attributes or {},
        "events": events or [],
        "children": [],
    }


def _from_rows(rows: Sequence[Any]) -> List[Dict[str, Any]]:
    return [
        _node(
            row_id=str(row.id),
            span_id=row.span_id,
            parent_span_id=row.parent_span_id,
            span_name=row.span_name,
            span_kind=row.span_kind,
            span_type=row.span_type,
            start_time=row.start_time,
            end_time=row.end_time,
            status_code=row.status_code,
            status_message=row.status_message,
            attributes=row.attributes,
            events=row.events,
        )
        for row in rows
    ]


def _from_otel(spans: Iterable[OTELSpan]) -> List[Dict[str, Any]]:
    return [
        _node(
            row_id=None,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            span_name=span.span_name,
            span_kind=span.span_kind.value,
            span_type=None,
            start_time=span.start_time,
            end_time=span.end_time,
            status_code=span.status_code.value,
            status_message=span.status_message,
            attributes=span.attributes,
            events=[event.model_dump() for event in span.events],
        )
        for span in spans
    ]


def _trace(trace_id: str, project_id: str, nodes: List[Dict[str, Any]]) -> Trace:
    """Nest the nodes into a tree (children by start time) and wrap them in a Trace.

    Not ``tree_builder.build_span_tree``: that takes stored rows only, and these nodes mix
    stored rows with spans a batch run has not written yet.
    """
    by_id = {node["span_id"]: node for node in nodes}
    roots = []
    for node in nodes:
        parent = by_id.get(node.pop("parent_span_id"))
        (parent["children"] if parent else roots).append(node)
    for node in nodes:
        node["children"].sort(key=lambda child: child["start_time"])
    roots.sort(key=lambda root: root["start_time"])
    return Trace.model_validate(
        {"trace_id": trace_id, "project_id": project_id, "root_spans": roots}
    )


def load_evaluation_trace(
    trace_id: str,
    organization_id: str,
    project_id: str,
    user_id: str = "",
    unsaved_spans: Sequence[OTELSpan] = (),
) -> Optional[Trace]:
    """The trace with this id, read from storage in a session of its own.

    ``unsaved_spans`` stand in when nothing is stored yet: a batch run writes its invocation
    spans only after scoring, and those are exactly the spans it will write.
    """
    with get_db_with_tenant_variables(organization_id, user_id, project_id) as db:
        rows = get_trace_by_id(
            db, trace_id=trace_id, project_id=project_id, organization_id=organization_id
        )
        nodes = _from_rows(rows)

    # Both at once: a service that received the traceparent may have stored its spans
    # while the invocation span above them is still waiting to be written.
    stored = {node["span_id"] for node in nodes}
    nodes += _from_otel(
        span for span in unsaved_spans if span.trace_id == trace_id and span.span_id not in stored
    )
    if not nodes:
        logger.debug("No spans for trace %s to evaluate", trace_id)
        return None
    return _trace(trace_id, project_id, nodes)


def trace_from_response(
    input_text: str,
    output_text: str,
    context: Optional[List[str]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Trace:
    """A trace built from the request and response alone, for an evaluation with nothing
    stored: tracing off, an older SDK, or an endpoint without a project.

    One invocation span, marked ``rhesis.trace.source = "response"``, with the reported tool
    calls and context as its children: the same shape a stored REST invocation has.
    """
    return Trace.from_response(
        input_text, output_text, context=context, tool_calls=tool_calls, metadata=metadata
    )


def with_live_values(
    trace: Trace,
    input_text: str,
    output_text: str,
    context: Optional[List[str]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Trace:
    """Put what the evaluation itself received on the trace's root.

    The input and output replace the stored copies, which are cut at ``MAX_IO_LENGTH``: a
    metric must judge the whole answer. Reported tool calls become child spans only where the
    trace has no tool span, so a call never counts twice. Reported context always does:
    ``Trace.context`` prefers it, because it is the full text and a recorded retrieval is not.
    """
    root = trace.root_spans[0] if trace.root_spans else None
    if root is None:
        return trace
    root.attributes[ConversationAttributes.CONVERSATION_INPUT] = input_text
    root.attributes[ConversationAttributes.CONVERSATION_OUTPUT] = output_text
    if metadata:
        root.attributes[EndpointAttributes.RESPONSE_METADATA] = json.dumps(metadata, default=str)

    reported = {
        "tool_calls": None if trace.spans(kind="tool.invoke") else tool_calls,
        "context": context,
    }
    if not any(reported.values()):
        return trace
    # Only lends its ids and times to the children; the root itself is not rebuilt.
    start = root.start_time or datetime.now(timezone.utc)
    parent = OTELSpan(
        trace_id=trace.trace_id or secrets.token_hex(16),
        span_id=root.span_id or secrets.token_hex(8),
        span_name="function.endpoint_invoke",
        start_time=start,
        end_time=root.end_time or start,
    )
    for node in _from_otel(reported_spans(reported, parent)):
        node.pop("parent_span_id")
        root.children.append(Span.model_validate(node))
    return trace


def evaluation_trace_loader(
    result: Any,
    organization_id: Optional[str],
    project_id: Optional[str],
    user_id: Optional[str] = None,
    unsaved_spans: Sequence[OTELSpan] = (),
):
    """A loader for ``MetricEvaluator`` that reads the trace an endpoint result points at,
    or None when the result carries no trace id (tracing off, or an old SDK).

    A result read from an existing trace names that trace's project, which wins over the
    endpoint's.
    """
    trace_id = result.get("trace_id") if isinstance(result, dict) else None
    if trace_id:
        project_id = result.get("trace_project_id") or project_id
    if not (trace_id and organization_id and project_id):
        return None
    return lambda: load_evaluation_trace(
        trace_id, organization_id, project_id, user_id or "", unsaved_spans
    )
