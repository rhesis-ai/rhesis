"""Virtual sort fields for a test run's token and cost totals.

Sibling of ``count_sort.py``, with one structural difference worth knowing. A count is a
single aggregate, so it fits in a correlated scalar subquery. Usage is two aggregates --
collapse the enrichment blob per trace, then sum those traces per run -- and a subquery
in a FROM clause cannot reference the outer query without LATERAL. So this joins a
standalone grouped subquery rather than correlating one.

The join produces at most one row per run, so it cannot duplicate the rows being ordered.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Query, Session

MODEL_SORT_FIELD = "model"

# The sort fields the API accepts, which are also what the grid columns are called.
# Names only, no SQL imports: query_validation imports this module at import time, and
# reaching into app.crud from there pulls the whole model layer back through a
# half-initialised query_utils. The expressions are resolved in _sum_expression instead.
VIRTUAL_USAGE_SORT_FIELDS = frozenset(
    {
        "total_tokens",
        "total_input_tokens",
        "total_output_tokens",
        "total_cost_usd",
        "total_input_cost_usd",
        "total_output_cost_usd",
        MODEL_SORT_FIELD,
    }
)


def _sum_expression(sort_by: str, per_trace):
    """The per-trace column a run's total is summed from."""
    from rhesis.backend.app.crud.usage_sql import (
        coalesced_input_tokens,
        coalesced_output_tokens,
        coalesced_tokens,
    )

    if sort_by == "total_tokens":
        return coalesced_tokens(per_trace)
    if sort_by == "total_input_tokens":
        return coalesced_input_tokens(per_trace)
    if sort_by == "total_output_tokens":
        return coalesced_output_tokens(per_trace)
    return getattr(per_trace.c, sort_by.removeprefix("total_"))


def is_virtual_usage_sort(sort_by: Optional[str]) -> bool:
    return sort_by in VIRTUAL_USAGE_SORT_FIELDS


def model_supports_usage_sort(model, sort_by: str) -> bool:
    """Only the entity traces are stamped against can be ordered by what it spent.

    Asked of the foreign key rather than of the ``traces`` backref, which SQLAlchemy does
    not attach to TestRun until mappers are configured -- and validation can run before
    that, which would reject every usage sort as unsupported.
    """
    if sort_by not in VIRTUAL_USAGE_SORT_FIELDS:
        return False

    from rhesis.backend.app.models.trace import Trace

    table = getattr(model, "__tablename__", None)
    return any(fk.column.table.name == table for fk in Trace.__table__.c.test_run_id.foreign_keys)


def _trace_base(db: Session, organization_id: Optional[str]):
    """Every trace stamped with a test run, within one organization.

    The tenant filter is explicit rather than left to the ORM auto-filter: this becomes a
    plain subquery nested inside the statement being executed, and ``auto_filter`` adds
    its criteria to ORM entities in that statement, not to subqueries built beforehand.
    Getting this wrong would let one organization order its list by another's spending.
    """
    from rhesis.backend.app import models as app_models

    filters = [
        app_models.Trace.test_run_id.isnot(None),
        app_models.Trace.deleted_at.is_(None),
    ]
    if organization_id:
        filters.append(app_models.Trace.organization_id == UUID(str(organization_id)))
    return db.query(app_models.Trace).filter(*filters).subquery()


def _usage_subquery(db: Session, sort_by: str, organization_id: Optional[str]):
    """One row per test run, carrying just the figure being sorted on."""
    from rhesis.backend.app.crud.usage_sql import models_used_select, per_trace_usage_subquery

    base = _trace_base(db, organization_id)

    if sort_by == MODEL_SORT_FIELD:
        # Alphabetically first, which is the model the grid cell shows before its "+N".
        pairs = models_used_select(base, extra_columns=(base.c.test_run_id,)).subquery()
        return (
            select(
                pairs.c.test_run_id.label("test_run_id"),
                func.min(pairs.c.model_name).label("value"),
            )
            .group_by(pairs.c.test_run_id)
            .subquery()
        )

    per_trace = per_trace_usage_subquery(db, base, extra_group_by=(base.c.test_run_id,))
    return (
        select(
            per_trace.c.test_run_id.label("test_run_id"),
            func.sum(_sum_expression(sort_by, per_trace)).label("value"),
        )
        .group_by(per_trace.c.test_run_id)
        .subquery()
    )


def apply_virtual_usage_sort(
    query: Query,
    model,
    sort_by: str,
    sort_order: str,
    db: Session,
    organization_id: Optional[str] = None,
) -> Query:
    """Order *query* by a per-run usage total, joined rather than correlated."""
    if not model_supports_usage_sort(model, sort_by):
        return query

    usage = _usage_subquery(db, sort_by, organization_id)
    ordered = desc(usage.c.value) if sort_order == "desc" else asc(usage.c.value)

    # nullslast so a run with no traces sinks to the bottom either way, rather than
    # leading a "most expensive first" list on Postgres' NULLS FIRST default for DESC.
    return query.outerjoin(usage, usage.c.test_run_id == model.id).order_by(ordered.nullslast())
