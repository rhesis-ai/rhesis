"""Usage accounting service.

Tracks actual consumption per organization per :class:`QuotaResource`.

Two kinds of resource:

- **Flow resources** (``TEST_EXECUTIONS``, ``TEST_GENERATION``,
  ``TRACING_SPANS``, ``MODEL_TOKENS``): cumulative counters for the
  current calendar-month billing period, stored in the ``usage`` table
  and incremented atomically by :func:`increment_usage`.
- **Stock resources** (``SEATS``, ``PROJECTS``, ``ENDPOINTS``): a live
  count of existing entities -- there is nothing to accrue or reset
  monthly, so these are computed on read via ``count_org_*``.

:func:`get_usage_summary` merges both kinds against
:class:`~rhesis.backend.app.quota.QuotaRegistry` limits for the
read-only ``GET /usage`` endpoint.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.usage import Usage
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaRegistry, QuotaResource
from rhesis.backend.app.scope import bypass_tenant_filter

logger = logging.getLogger(__name__)

_USAGE_CONFLICT_INDEX = ["organization_id", "resource", "period_start"]

FLOW_KIND = "flow"
STOCK_KIND = "stock"


def _current_period(today: Optional[date] = None) -> tuple[date, date]:
    """Return ``(period_start, period_end)`` for the calendar month containing *today*.

    Anchored to UTC rather than the host's local date. Billing periods must
    not depend on which timezone a worker happens to run in: with local
    dates, a worker in UTC+13 and one in UTC-8 disagree about which month a
    call near midnight belongs to, and would accrue against two different
    rows for the same instant.
    """
    today = today or datetime.now(timezone.utc).date()
    period_start = today.replace(day=1)
    last_day = monthrange(today.year, today.month)[1]
    period_end = today.replace(day=last_day)
    return period_start, period_end


def dispatch_accrual(
    organization_id: Optional[str], resource: QuotaResource, amount: int = 1
) -> None:
    """Queue an accrual of *amount* against *resource* for *organization_id*.

    **This is the only entry point call sites should use.**
    :func:`increment_usage` is the database primitive behind it and is
    called solely by the worker task.

    Fire-and-forget, for two reasons:

    - *It must not be able to break the thing it is measuring.* Accrual is
      bookkeeping attached to some primary operation (a test run, a span
      batch, an LLM call). Writing inline made a failed counter write fail
      that operation -- in ``post_ingest_link`` a raised ``increment_usage``
      was caught by the task's blanket ``except`` and retried the entire
      body, re-dispatching enrichment for spans that had already been
      linked. Here, a dispatch failure is logged and swallowed; the caller
      never sees it.
    - *It must not add latency to interactive requests.* The callback wired
      into hosted models (see
      ``rhesis.backend.app.utils.usage_tracking``) fires on request paths a
      user is waiting on -- explorer suggestions, Architect chat, metric
      evaluation. ``.delay()`` publishes a broker message and returns; the
      connection checkout, RLS ``SET``, and upsert all happen on a worker.

    A queued task also gets Celery's retry policy, which an inline write in
    someone else's transaction never had.
    """
    if amount <= 0 or not organization_id:
        return

    # Imported lazily, not at module scope: `tasks/__init__.py` eagerly
    # imports every task module, and `tasks.usage` imports this module back
    # for `increment_usage`. A module-scope import here would be circular,
    # and would also drag the whole Celery app graph into any request that
    # merely touches the usage service.
    from rhesis.backend.tasks.usage import accrue_usage

    try:
        accrue_usage.delay(str(organization_id), resource.value, amount)
    except Exception:
        logger.warning(
            "Failed to queue %s accrual (amount=%s) for org %s",
            resource.value,
            amount,
            organization_id,
            exc_info=True,
        )


def increment_usage(
    db: Session, org_id: Optional[str], resource: QuotaResource, amount: int = 1
) -> None:
    """Atomically add *amount* to the org's counter for *resource* in the current period.

    The database primitive behind :func:`dispatch_accrual`, and called only
    by the ``accrue_usage`` worker task. Call ``dispatch_accrual`` instead
    unless you are that task: this function commits *db*, which means
    calling it with a session borrowed from some other unit of work commits
    that work too, and it raises on failure, which in a Celery task body
    means retrying whatever else that task does.

    A single ``INSERT ... ON CONFLICT DO UPDATE`` (upsert): creates the
    period row with ``used = amount`` if absent, or adds *amount* to the
    existing row if present, all in one statement. This replaced an earlier
    UPDATE-then-fallback-INSERT design that had a real race: two workers
    missing the UPDATE at the same instant would both attempt to create the
    row, and the second would hit ``uq_usage_org_resource_period`` and raise
    instead of accruing. Concurrent Celery workers accruing the same
    org/resource/period are the normal case, not an edge case, so this needs
    to be genuinely atomic rather than retried.

    Requires the session's ``app.current_organization`` GUC to match
    *org_id*: ``usage`` has a FORCE'd ``tenant_isolation`` RLS policy whose
    ``USING`` clause Postgres also applies as the ``WITH CHECK`` for
    inserts, so an unbound or mismatched scope makes this raise rather than
    write to the wrong tenant. The task binds scope before calling.

    No-ops on ``amount <= 0`` or a falsy ``org_id`` (e.g. a task whose
    tenant context never resolved) -- silently skipping is correct here:
    there is no organization to attribute the usage to, and casting an
    empty string to ``uuid`` would raise.
    """
    if amount <= 0 or not org_id:
        return

    period_start, period_end = _current_period()
    stmt = (
        pg_insert(Usage.__table__)
        .values(
            organization_id=org_id,
            resource=resource.value,
            period_start=period_start,
            period_end=period_end,
            used=amount,
        )
        .on_conflict_do_update(
            index_elements=_USAGE_CONFLICT_INDEX,
            set_={
                "used": Usage.__table__.c.used + amount,
                "updated_at": func.now(),
            },
        )
    )
    db.execute(stmt)
    db.commit()


def _count_org_rows(db: Session, model, org_id: str, *, exclude_deleted: bool) -> int:
    """Live ``COUNT(*)`` of *model* rows belonging to *org_id*.

    Shared by the stock-resource counters below -- they differ only in
    which model to count and whether soft-deleted rows should be excluded.
    """
    with bypass_tenant_filter():
        filters = [model.organization_id == org_id]
        if exclude_deleted:
            filters.append(model.deleted_at.is_(None))
        return db.query(func.count(model.id)).filter(*filters).scalar() or 0


def count_org_seats(db: Session, org_id: str) -> int:
    """Count users whose ``organization_id`` points to *org_id*.

    Removed users have ``organization_id`` set to ``NULL`` (they become
    orgless, not soft-deleted), so no ``deleted_at`` filter is applied.
    """
    return _count_org_rows(db, User, org_id, exclude_deleted=False)


def count_org_projects(db: Session, org_id: str) -> int:
    """Count non-deleted projects belonging to *org_id*."""
    return _count_org_rows(db, Project, org_id, exclude_deleted=True)


def count_org_endpoints(db: Session, org_id: str) -> int:
    """Count non-deleted endpoints belonging to *org_id*."""
    return _count_org_rows(db, Endpoint, org_id, exclude_deleted=True)


_STOCK_COUNTERS = {
    QuotaResource.SEATS: count_org_seats,
    QuotaResource.PROJECTS: count_org_projects,
    QuotaResource.ENDPOINTS: count_org_endpoints,
}


def get_usage_summary(db: Session, org_id: str, org: Optional[Organization]) -> dict:
    """Return ``{resources: {<resource>: {used, limit, period_start, period_end, kind}}, edition}``.

    Flow resources report cumulative usage from the ``usage`` table for the
    current billing period. Stock resources report a live entity count.
    Every :class:`QuotaResource` member is present in the response, even
    when its usage is zero. ``kind`` (``"flow"`` or ``"stock"``) lets the
    frontend group resources without duplicating the flow/stock split as a
    second, hand-maintained list.
    """
    period_start, period_end = _current_period()
    limits = QuotaRegistry.get_limits(org)

    with bypass_tenant_filter():
        flow_used = {
            row.resource: row.used
            for row in db.query(Usage).filter(
                Usage.organization_id == org_id,
                Usage.period_start == period_start,
            )
        }

    resources: dict[str, dict] = {}
    for resource in QuotaResource:
        counter = _STOCK_COUNTERS.get(resource)
        used = counter(db, org_id) if counter is not None else flow_used.get(resource.value, 0)
        resources[resource.value] = {
            "used": used,
            "limit": limits.get(resource),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "kind": STOCK_KIND if counter is not None else FLOW_KIND,
        }

    edition = str(FeatureRegistry.license_info(org=org).get("edition", "community"))
    return {"resources": resources, "edition": edition}


def _recent_period_starts(months: int, today: Optional[date] = None) -> list[date]:
    """Return the first-of-month date for each of the last *months* calendar
    months, oldest first, ending with the month containing *today*."""
    today = today or datetime.now(timezone.utc).date()
    year, month = today.year, today.month
    starts = []
    for _ in range(months):
        starts.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return list(reversed(starts))


def get_usage_history(db: Session, org_id: str, months: int = 6) -> dict:
    """Return ``{resources: {<flow resource>: [{period_start, used}, ...]}}``.

    One point per calendar month for each flow resource, oldest first,
    covering the trailing *months* months including the current one.
    Stock resources are excluded: they are live counts with no historical
    row to chart (see ``get_usage_summary``'s docstring for the flow/stock
    split). Months with no accrual get an explicit ``used: 0`` point rather
    than being omitted, so the frontend can plot a continuous line without
    its own gap-filling logic.

    Comparing ``Usage.period_start`` (a plain ``Date`` column) against
    plain ``date`` objects here carries none of the timestamptz/session-
    timezone risk that a raw-SQL migration comparing against a
    ``timestamptz`` column would -- see 91607f0dd412's fix for that
    specific class of bug, which does not apply to this comparison.
    """
    period_starts = _recent_period_starts(months)

    with bypass_tenant_filter():
        rows = db.query(Usage).filter(
            Usage.organization_id == org_id,
            Usage.period_start >= period_starts[0],
        )
        used_by_key = {(row.resource, row.period_start): row.used for row in rows}

    history: dict[str, list[dict]] = {}
    for resource in QuotaResource:
        if resource in _STOCK_COUNTERS:
            continue
        history[resource.value] = [
            {
                "period_start": period_start.isoformat(),
                "used": used_by_key.get((resource.value, period_start), 0),
            }
            for period_start in period_starts
        ]

    return {"resources": history}
