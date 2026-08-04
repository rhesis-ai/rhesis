"""Validate a request against the registry and run exactly one GROUP BY query.

Every param is checked against the registry before it touches SQL: an
unknown entity, group_by, measure, or filter raises InsightsValidationError
(400) instead of reaching the database.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.services.stats.common import parse_date_range

from .registry import REGISTRY

MAX_BATCH_QUERIES = 10


class InsightsValidationError(ValueError):
    """Raised when a request references an entity/dimension/measure/filter
    that isn't declared in the registry."""


def _entry(entity: str) -> dict:
    entry = REGISTRY.get(entity)
    if entry is None:
        raise InsightsValidationError(f"Unknown entity '{entity}'. Available: {sorted(REGISTRY)}")
    return entry


def build_query(
    db: Session,
    entity: str,
    group_by: List[str],
    measures: List[str],
    filters: Optional[Dict[str, list]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    organization_id: Optional[str] = None,
):
    """Return a validated, filtered, grouped SQLAlchemy query to be executed."""
    entry = _entry(entity)

    unknown_dims = set(group_by) - set(entry["dimensions"])
    if unknown_dims:
        raise InsightsValidationError(
            f"Unknown group_by {sorted(unknown_dims)} for entity '{entity}'. "
            f"Available: {sorted(entry['dimensions'])}"
        )
    if not measures:
        raise InsightsValidationError("At least one measure is required")
    unknown_measures = set(measures) - set(entry["measures"])
    if unknown_measures:
        raise InsightsValidationError(
            f"Unknown measures {sorted(unknown_measures)} for entity '{entity}'. "
            f"Available: {sorted(entry['measures'])}"
        )

    view = entry["view"]
    q = db.query(view)

    if organization_id is not None:
        q = q.filter(view.organization_id == organization_id)

    for key, values in (filters or {}).items():
        if not values:
            continue
        if key in entry["subquery_filters"]:
            id_column, build_subquery = entry["subquery_filters"][key]
            q = q.filter(id_column.in_(build_subquery(db, values)))
        elif key in entry["filters"]:
            q = q.filter(entry["filters"][key].in_(values))
        else:
            raise InsightsValidationError(
                f"Unknown filter '{key}' for entity '{entity}'. "
                f"Available: {sorted(set(entry['filters']) | set(entry['subquery_filters']))}"
            )

    date_column = entry.get("date_column")
    if start_date is not None and date_column is not None:
        q = q.filter(date_column >= start_date)
    if end_date is not None and date_column is not None:
        q = q.filter(date_column <= end_date)

    group_cols = [entry["dimensions"][g].label(g) for g in group_by]
    measure_cols = [entry["measures"][m]().label(m) for m in measures]
    q = q.with_entities(*group_cols, *measure_cols)
    if group_cols:
        q = q.group_by(*(entry["dimensions"][g] for g in group_by))

    return q


def run_query(
    db: Session,
    entity: str,
    group_by: List[str],
    measures: List[str],
    filters: Optional[Dict[str, list]] = None,
    months: int = 6,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the query and shape results into the uniform insights envelope."""
    try:
        start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)
    except ValueError as exc:
        raise InsightsValidationError(f"Invalid start_date/end_date: {exc}") from exc
    q = build_query(
        db, entity, group_by, measures, filters, start_date_obj, end_date_obj, organization_id
    )

    rows = []
    for r in q.all():
        row = {dim: getattr(r, dim) for dim in group_by}
        row.update({measure: getattr(r, measure) for measure in measures})
        rows.append(row)

    return {
        "entity": entity,
        "dimensions": group_by,
        "measures": measures,
        "rows": rows,
    }


def run_batch(
    db: Session, queries: Dict[str, Any], organization_id: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """Run several named sub-queries in one call and return one envelope per label.

    Callers combine the per-label envelopes themselves (e.g. zipping a test_result-grain
    breakdown with a metric-grain one by a shared dimension like behavior).
    """
    if not queries:
        raise InsightsValidationError("At least one query is required")
    if len(queries) > MAX_BATCH_QUERIES:
        raise InsightsValidationError(
            f"Too many queries ({len(queries)}); max {MAX_BATCH_QUERIES} per request"
        )

    return {
        label: run_query(
            db,
            entity=q.entity,
            group_by=q.group_by,
            measures=q.measures,
            filters=q.filters,
            months=q.months,
            start_date=q.start_date,
            end_date=q.end_date,
            organization_id=organization_id,
        )
        for label, q in queries.items()
    }
