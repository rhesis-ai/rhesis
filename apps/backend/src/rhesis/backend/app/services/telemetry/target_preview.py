"""What a metric's target picks in a project's latest traces, before the metric runs.

The traces are built as evaluation builds them and matched with the SDK's ``Target.select``,
so the preview counts exactly the units a metric would be run on.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.telemetry import load_trace_spans, recent_trace_ids
from rhesis.backend.app.schemas.metric import TargetPreview, TargetPreviewSample
from rhesis.backend.app.services.telemetry.evaluation_trace import stored_trace
from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.metrics.arguments import judged_input_output
from rhesis.sdk.metrics.conditions import span_status, text
from rhesis.sdk.metrics.targets import Target, TargetKind, Unit

#: Units shown as examples, and how much of each one's input and output.
PREVIEW_SAMPLES = 5
PREVIEW_TEXT_LIMIT = 500
_CUT_MARK = "…"


def _cut(value: Any) -> Optional[str]:
    if value is None:
        return None
    shown = text(value)
    if len(shown) <= PREVIEW_TEXT_LIMIT:
        return shown
    return shown[: PREVIEW_TEXT_LIMIT - len(_CUT_MARK)] + _CUT_MARK


def _sample(trace: Trace, unit: Unit) -> TargetPreviewSample:
    """A unit as an example. A unit of the whole trace (the conversation, the run) has no span
    of its own: it shows the trace's first root, and the input and output a metric would read."""
    span: Optional[Span] = unit.span
    if span is None:
        span = trace.root_spans[0] if trace.root_spans else None
        unit_input, unit_output = judged_input_output(trace)
    else:
        unit_input, unit_output = unit.input, unit.output
    return TargetPreviewSample(
        trace_id=trace.trace_id,
        span_id=span.span_id if span else None,
        name=unit.name or (span.span_name if span else None),
        input=_cut(unit_input),
        output=_cut(unit_output),
        duration_ms=span.duration_ms if span else None,
        status=span_status(span.status_code).value if span else None,
    )


def _units(target: Target, trace: Optional[Trace]) -> List[Unit]:
    """What evaluation judges in ``trace``: a conversation target runs only on a trace that
    is a conversation (the evaluator checks before it runs the metric), else it's not
    applicable."""
    if trace is None:
        return []
    if target.on is TargetKind.CONVERSATION and not trace.is_conversation:
        return []
    return target.select(trace)


def _rows_by_trace(rows: Sequence[Any]) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = defaultdict(list)
    for row in rows:
        grouped[row.trace_id].append(row)
    return grouped


def preview_target(db: Session, project_id: str, target: Target, traces: int) -> TargetPreview:
    """Match ``target`` on the project's ``traces`` latest traces: one query for their ids,
    one for all their spans. ``db`` must be scoped to the project, so RLS lets its rows through."""
    trace_ids = recent_trace_ids(db, project_id, traces)
    rows = _rows_by_trace(load_trace_spans(db, trace_ids, project_id))
    matching_traces = units = 0
    samples: List[TargetPreviewSample] = []
    for trace_id in trace_ids:
        trace = stored_trace(trace_id, project_id, rows.get(trace_id, ()))
        picked = _units(target, trace)
        if not picked:
            continue
        matching_traces += 1
        units += len(picked)
        samples += [_sample(trace, unit) for unit in picked[: PREVIEW_SAMPLES - len(samples)]]
    return TargetPreview(
        traces=len(trace_ids),
        matching_traces=matching_traces,
        units=units,
        not_applicable_traces=len(trace_ids) - matching_traces,
        samples=samples,
        target_summary=target.describe(),
        target_summary_short=target.describe(short=True),
    )
