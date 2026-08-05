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
VALID_OUTCOMES = frozenset({"pass", "fail", "all"})


class InsightsValidationError(ValueError):
    """Raised when a request references an entity/dimension/measure/filter
    that isn't declared in the registry."""


def _entry(entity: str) -> dict:
    entry = REGISTRY.get(entity)
    if entry is None:
        raise InsightsValidationError(f"Unknown entity '{entity}'. Available: {sorted(REGISTRY)}")
    return entry


def _apply_filters(q, db: Session, entity: str, entry: dict, filters: Optional[Dict[str, list]]):
    """Apply registry-declared filters (and subquery filters) to a base query."""
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
    return q


def _apply_date_range(q, entry: dict, start_date: Optional[datetime], end_date: Optional[datetime]):
    date_column = entry.get("date_column")
    if start_date is not None and date_column is not None:
        q = q.filter(date_column >= start_date)
    if end_date is not None and date_column is not None:
        q = q.filter(date_column <= end_date)
    return q


def _base_query(
    db: Session,
    entity: str,
    filters: Optional[Dict[str, list]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    organization_id: Optional[str] = None,
):
    """Filtered view query shared by aggregation and ID resolution.

    Returns (entry, view, query) — callers add GROUP BY / DISTINCT on top.
    """
    entry = _entry(entity)
    view = entry["view"]
    q = db.query(view)

    if organization_id is not None:
        q = q.filter(view.organization_id == organization_id)

    q = _apply_filters(q, db, entity, entry, filters)
    q = _apply_date_range(q, entry, start_date, end_date)
    return entry, view, q


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
    entry, _view, q = _base_query(db, entity, filters, start_date, end_date, organization_id)

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
    months: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the query and shape results into the uniform insights envelope."""
    try:
        start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)
    except ValueError as exc:
        raise InsightsValidationError(str(exc)) from exc
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


def run_queries(
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


def run_ids(
    db: Session,
    entity: str,
    filters: Optional[Dict[str, list]] = None,
    outcome: str = "all",
    months: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return distinct IDs matching the same filter universe as GET /insights.

    outcome ('pass'/'fail'/'all') uses the entity's registry apply_outcome when set.
    Dimension filters (behavior_ids, topic_ids, metric_names, …) go through the
    normal registry filters — no name-based special cases.
    """
    if outcome not in VALID_OUTCOMES:
        raise InsightsValidationError(
            f"Invalid outcome '{outcome}'. Available: {sorted(VALID_OUTCOMES)}"
        )

    try:
        start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)
    except ValueError as exc:
        raise InsightsValidationError(str(exc)) from exc
    entry, view, q = _base_query(db, entity, filters, start_date_obj, end_date_obj, organization_id)

    id_column = entry.get("id_column")
    if id_column is None:
        raise InsightsValidationError(f"Entity '{entity}' does not support /insights/ids")

    if outcome != "all":
        apply_outcome = entry.get("apply_outcome")
        if apply_outcome is None:
            raise InsightsValidationError(
                f"outcome filter is not supported for entity '{entity}'. "
                "Use entity=test_result or entity=metric."
            )
        q = q.filter(apply_outcome(view, outcome))

    rows = q.with_entities(id_column).distinct().all()
    return {
        "entity": entity,
        "ids": [str(row[0]) for row in rows if row[0] is not None],
    }
