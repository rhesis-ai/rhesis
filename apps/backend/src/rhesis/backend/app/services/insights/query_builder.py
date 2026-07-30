"""Validate a request against the registry and run exactly one GROUP BY query.

Every param is checked against the registry before it touches SQL: an
unknown entity, group_by, measure, or filter raises InsightsValidationError
(400) instead of reaching the database.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .registry import REGISTRY


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
):
    """Return a validated, filtered, grouped SQLAlchemy query -- not yet executed."""
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
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Execute the query and shape results into the uniform insights envelope."""
    q = build_query(db, entity, group_by, measures, filters, start_date, end_date)

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
