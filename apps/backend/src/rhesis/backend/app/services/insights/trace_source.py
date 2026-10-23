"""One row per trace, for the insights `trace` entity.

Unlike the other entities this is not a database view: tokens and cost come from
crud/usage_sql.py's per-trace collapse, so insights reports the same figure for a
trace as the traces list and GET /telemetry/metrics. The trace's own fields come
from its first root span, which is the canonical one when a trace has several.
"""

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.usage_sql import (
    coalesced_input_tokens,
    coalesced_output_tokens,
    coalesced_tokens,
    per_trace_usage_subquery,
)


def trace_stats(db: Session):
    T = models.Trace
    spans = db.query(T).filter(T.deleted_at.is_(None)).subquery("trace_spans")

    roots = (
        db.query(
            spans.c.trace_id,
            spans.c.organization_id,
            spans.c.project_id,
            spans.c.environment,
            spans.c.start_time,
            spans.c.duration_ms,
            spans.c.span_name,
            spans.c.test_run_id,
        )
        .filter(spans.c.parent_span_id.is_(None))
        .distinct(spans.c.trace_id)
        .order_by(spans.c.trace_id, spans.c.start_time)
        .subquery("trace_roots")
    )
    errors = (
        db.query(
            spans.c.trace_id,
            func.bool_or(spans.c.status_code == "ERROR").label("has_error"),
        )
        .group_by(spans.c.trace_id)
        .subquery("trace_errors")
    )
    usage = per_trace_usage_subquery(db, spans)

    TR, TC, E = models.TestRun, models.TestConfiguration, models.Endpoint
    return (
        db.query(
            roots.c.trace_id,
            roots.c.organization_id,
            roots.c.project_id,
            roots.c.environment,
            roots.c.start_time,
            roots.c.duration_ms,
            roots.c.span_name.label("operation"),
            errors.c.has_error,
            case((errors.c.has_error, 1), else_=0).label("error_flag"),
            roots.c.test_run_id,
            TR.name.label("test_run_name"),
            TC.endpoint_id,
            E.name.label("endpoint_name"),
            coalesced_tokens(usage).label("tokens"),
            coalesced_input_tokens(usage).label("input_tokens"),
            coalesced_output_tokens(usage).label("output_tokens"),
            usage.c.cost_usd,
        )
        .join(errors, errors.c.trace_id == roots.c.trace_id)
        .join(usage, usage.c.trace_id == roots.c.trace_id)
        .outerjoin(TR, TR.id == roots.c.test_run_id)
        .outerjoin(TC, TC.id == TR.test_configuration_id)
        .outerjoin(E, E.id == TC.endpoint_id)
        .subquery("trace_stats")
    )
