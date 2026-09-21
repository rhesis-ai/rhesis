"""Record a verdict on a trace an instrumented application just produced.

The platform stores every span as a row with its own UUID, and that row id is
what addresses an annotation. An application that produced the trace knows only
the OTEL trace id, so these helpers annotate by that instead and let the server
resolve it to the trace's root span.

The point is feedback that arrives from outside the platform: a thumbs-down
from an end user, a QA harness, an eval script. It lands as an ordinary
annotation, so a Pass/Fail verdict overrides the trace's automated outcome and
shows up wherever annotations already do.

    from rhesis.sdk.telemetry import annotate_current_trace

    answer = my_agent(question)
    if user_said_it_was_wrong:
        annotate_current_trace("fail", "Cited a document that does not exist.")

Ingestion is asynchronous, so a trace recorded moments ago may not be queryable
yet, and the call raises rather than pretending it landed. Annotating after the
request returns leaves more time for the spans to arrive but guarantees nothing,
so a caller that annotates close to the request should be ready to retry: the
error says the trace is not ingested yet, and is distinct from a wrong id.
"""

from typing import Optional, Union

from rhesis.sdk.entities.annotation import (
    AnnotatableEntity,
    Annotation,
    Verdict,
    resolve_verdict,
    turn_reference,
)
from rhesis.telemetry.context import get_root_trace_id

__all__ = ["annotate_trace", "annotate_current_trace"]


def annotate_trace(
    trace_id: str,
    verdict: Union[Verdict, str],
    comment: Optional[str] = None,
    *,
    metric: Optional[str] = None,
    turn: Optional[Union[int, str]] = None,
) -> Annotation:
    """Record a verdict on the trace with this OTEL trace id.

    ``trace_id`` is the 32-character hex id, not the span row id that
    ``Annotations.create`` takes. The server resolves it to the trace's root
    span, and raises if the trace has not been ingested yet.

    ``metric`` and ``turn`` are mutually exclusive: an annotation judges one
    thing. Naming neither judges the trace as a whole.
    """
    if metric and turn is not None:
        raise ValueError("An annotation targets a metric or a turn, not both")

    annotation = Annotation(
        entity_type=AnnotatableEntity.TRACE.value,
        trace_id=trace_id,
        status_id=resolve_verdict(verdict),
        comments=comment,
        target_type="metric" if metric else "turn" if turn is not None else None,
        target_reference=metric if metric else (turn_reference(turn) if turn is not None else None),
    )
    annotation.push()
    return annotation


def annotate_current_trace(
    verdict: Union[Verdict, str],
    comment: Optional[str] = None,
    *,
    metric: Optional[str] = None,
    turn: Optional[Union[int, str]] = None,
) -> Annotation:
    """Record a verdict on the trace this call is part of.

    Reads the trace id the tracer recorded for the current root, so it works
    after the span has closed -- which is when a human verdict usually arrives.
    Raises if there is no trace in context, because the alternative is
    annotating some other trace or silently doing nothing.
    """
    trace_id = get_root_trace_id()
    if not trace_id:
        raise ValueError(
            "No trace in context, so there is nothing to annotate. This runs "
            "inside an instrumented call; pass the id to annotate_trace() to "
            "annotate one from elsewhere."
        )
    return annotate_trace(trace_id, verdict, comment, metric=metric, turn=turn)
