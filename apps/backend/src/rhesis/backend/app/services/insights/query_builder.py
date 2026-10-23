"""Validate a request against the registry and run exactly one GROUP BY query.

Every param is checked against the registry before it touches SQL: an
unknown entity, group_by, measure, filter or order_by raises
InsightsValidationError (400) instead of reaching the database.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session

from rhesis.backend.app.services.insights.registry import (
    DEFAULT_TIME_GRAIN,
    PERIOD,
    REGISTRY,
    TIME_GRAINS,
    Entity,
)
from rhesis.backend.app.services.stats.common import parse_date_range

MAX_BATCH_QUERIES = 10
MAX_LIMIT = 1000
VALID_OUTCOMES = frozenset({"pass", "fail", "all"})


class InsightsValidationError(ValueError):
    """Raised when a request references an entity/dimension/measure/filter
    that isn't declared in the registry."""


def _entry(entity: str) -> Entity:
    entry = REGISTRY.get(entity)
    if entry is None:
        raise InsightsValidationError(f"Unknown entity '{entity}'. Available: {sorted(REGISTRY)}")
    return entry


class _Columns:
    """Resolves registry column references against the queried view or source.

    A view entity names its columns directly; a source entity names them as
    strings, which only exist once the source subquery has been built.
    """

    def __init__(self, entry: Entity, view: Any):
        self.entry = entry
        self.view = view

    def __call__(self, ref: Any) -> Any:
        return self.view.c[ref] if isinstance(ref, str) else ref

    def measure(self, name: str) -> Any:
        build = self.entry.measures[name].build
        return build(self.view.c) if self.entry.source else build()


def _apply_filters(q, db: Session, entity: str, cols: _Columns, filters: Optional[Dict[str, list]]):
    entry = cols.entry
    for key, values in (filters or {}).items():
        if not values:
            continue
        flt = entry.filters.get(key)
        if flt is None:
            raise InsightsValidationError(
                f"Unknown filter '{key}' for entity '{entity}'. Available: {sorted(entry.filters)}"
            )
        target = flt.subquery(db, values) if flt.subquery else values
        q = q.filter(cols(flt.column).in_(target))
    return q


def _apply_date_range(
    q, cols: _Columns, start_date: Optional[datetime], end_date: Optional[datetime]
):
    date_column = cols(cols.entry.date_column)
    if start_date is not None:
        q = q.filter(date_column >= start_date)
    if end_date is not None:
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

    Returns (columns, query) -- callers add GROUP BY / DISTINCT on top.
    """
    entry = _entry(entity)
    cols = _Columns(entry, entry.source(db) if entry.source else entry.view)
    q = db.query(cols.view)

    if organization_id is not None:
        org_column = cols("organization_id") if entry.source else entry.view.organization_id
        q = q.filter(org_column == organization_id)

    q = _apply_filters(q, db, entity, cols, filters)
    q = _apply_date_range(q, cols, start_date, end_date)
    return cols, q


def _period(cols: _Columns, time_grain: str):
    date_column = cols(cols.entry.date_column)
    return cast(func.date_trunc(time_grain, func.timezone("UTC", date_column)), Date)


def _group_columns(entity: str, cols: _Columns, group_by: List[str], time_grain: str):
    """(labelled select columns, group-by expressions, label -> expression)."""
    repeated = sorted({g for g in group_by if group_by.count(g) > 1})
    if repeated:
        raise InsightsValidationError(f"group_by lists {repeated} more than once; list each once")
    entry = cols.entry
    unknown = [g for g in group_by if g != PERIOD and g not in entry.dimensions]
    if unknown:
        raise InsightsValidationError(
            f"Unknown group_by {unknown} for entity '{entity}'. "
            f"Available: {sorted([PERIOD, *entry.dimensions])}"
        )
    if time_grain not in TIME_GRAINS:
        raise InsightsValidationError(
            f"Invalid time_grain '{time_grain}'. Available: {list(TIME_GRAINS)}"
        )

    selected, grouped, by_label = [], [], {}
    for name in group_by:
        if name == PERIOD:
            expr = _period(cols, time_grain)
            selected.append(expr.label(PERIOD))
            grouped.append(expr)
            by_label[PERIOD] = expr
            continue
        dim = entry.dimensions[name]
        if dim.id is not None:
            id_column = cols(dim.id)
            selected.append(id_column.label(f"{name}_id"))
            grouped.append(id_column)
        name_column = cols(dim.name)
        selected.append(name_column.label(name))
        grouped.append(name_column)
        by_label[name] = name_column
    return selected, grouped, by_label


def _order_columns(order_by: List[str], by_label: Dict[str, Any]):
    columns = []
    for key in order_by:
        descending = key.startswith("-")
        label = key.lstrip("-")
        expr = by_label.get(label)
        if expr is None:
            raise InsightsValidationError(
                f"Cannot order by '{label}': order_by must name a group_by dimension or a "
                f"requested measure. Available: {sorted(by_label)}"
            )
        columns.append(expr.desc().nulls_last() if descending else expr.asc().nulls_last())
    return columns


def build_query(
    db: Session,
    entity: str,
    group_by: List[str],
    measures: List[str],
    filters: Optional[Dict[str, list]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    organization_id: Optional[str] = None,
    time_grain: str = DEFAULT_TIME_GRAIN,
    order_by: Optional[List[str]] = None,
    limit: Optional[int] = None,
    min_count: Optional[int] = None,
):
    """Return a validated, filtered, grouped SQLAlchemy query to be executed."""
    cols, q = _base_query(db, entity, filters, start_date, end_date, organization_id)
    entry = cols.entry

    if not measures:
        raise InsightsValidationError("At least one measure is required")
    unknown_measures = sorted(set(measures) - set(entry.measures))
    if unknown_measures:
        raise InsightsValidationError(
            f"Unknown measures {unknown_measures} for entity '{entity}'. "
            f"Available: {sorted(entry.measures)}"
        )
    if limit is not None and not 1 <= limit <= MAX_LIMIT:
        raise InsightsValidationError(f"limit must be between 1 and {MAX_LIMIT}")
    if min_count is not None and min_count < 1:
        raise InsightsValidationError("min_count must be at least 1")

    selected, grouped, by_label = _group_columns(entity, cols, group_by, time_grain)
    measure_exprs = {m: cols.measure(m) for m in measures}
    by_label.update(measure_exprs)

    q = q.with_entities(*selected, *(expr.label(m) for m, expr in measure_exprs.items()))
    if grouped:
        q = q.group_by(*grouped)
    if min_count is not None:
        q = q.having(func.count() >= min_count)

    # Without an explicit order, rows come back sorted by the grouped labels so output is stable.
    order = _order_columns(order_by or group_by, by_label)
    if order:
        q = q.order_by(*order)
    if limit is not None:
        q = q.limit(limit)
    return q


def _row_keys(entry: Entity, group_by: List[str], measures: List[str]) -> List[str]:
    keys = []
    for name in group_by:
        dim = entry.dimensions.get(name)
        if dim is not None and dim.id is not None:
            keys.append(f"{name}_id")
        keys.append(name)
    return keys + list(measures)


def _json_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


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
    time_grain: str = DEFAULT_TIME_GRAIN,
    order_by: Optional[List[str]] = None,
    limit: Optional[int] = None,
    min_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute the query and shape results into the uniform insights envelope."""
    try:
        start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)
    except ValueError as exc:
        raise InsightsValidationError(str(exc)) from exc
    q = build_query(
        db,
        entity,
        group_by,
        measures,
        filters,
        start_date_obj,
        end_date_obj,
        organization_id,
        time_grain=time_grain,
        order_by=order_by,
        limit=limit,
        min_count=min_count,
    )

    keys = _row_keys(REGISTRY[entity], group_by, measures)
    rows = [{key: _json_value(getattr(r, key)) for key in keys} for r in q.all()]

    envelope = {"entity": entity, "dimensions": group_by, "measures": measures, "rows": rows}
    if PERIOD in group_by:
        envelope["time_grain"] = time_grain
    return envelope


def run_queries(
    db: Session, queries: Dict[str, Any], organization_id: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """Run several named sub-queries in one call and return one envelope per label.

    Callers combine the per-label envelopes themselves (e.g. zipping a test_result-grain
    breakdown with a metric-grain one by a shared dimension like requirement).
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
            time_grain=q.time_grain,
            order_by=q.order_by,
            limit=q.limit,
            min_count=q.min_count,
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
    """
    if outcome not in VALID_OUTCOMES:
        raise InsightsValidationError(
            f"Invalid outcome '{outcome}'. Available: {sorted(VALID_OUTCOMES)}"
        )

    try:
        start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)
    except ValueError as exc:
        raise InsightsValidationError(str(exc)) from exc
    cols, q = _base_query(db, entity, filters, start_date_obj, end_date_obj, organization_id)
    entry = cols.entry
    if entry.id_column is None:
        raise InsightsValidationError(f"Entity '{entity}' does not support /insights/ids")

    if outcome != "all":
        if entry.apply_outcome is None:
            outcome_entities = sorted(e for e, cfg in REGISTRY.items() if cfg.apply_outcome)
            raise InsightsValidationError(
                f"outcome filter is not supported for entity '{entity}'. "
                f"Use entity={' or entity='.join(outcome_entities)}."
            )
        q = q.filter(entry.apply_outcome(entry.view, outcome))

    rows = q.with_entities(entry.id_column).distinct().all()
    return {
        "entity": entity,
        "ids": [str(row[0]) for row in rows if row[0] is not None],
    }
