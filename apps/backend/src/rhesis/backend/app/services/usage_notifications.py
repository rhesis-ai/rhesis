"""Threshold-crossing notifications for quota usage.

Turns a change in a resource's usage into an in-app notification for the
org owner when the change just crossed 80% of the resource's `limit`, or
its `ceiling` -- not on every call once an org is already past a
threshold, only on the transition. Two entry points, one per resource kind:

- :func:`notify_flow_crossing`, from `services/usage.py:increment_usage`,
  for flow resources (test runs, test generation, tracing spans, model
  tokens) -- the accrual write itself is the natural before/after point.
- :func:`notify_stock_crossing`, from the three stock-resource creation
  routes (project, endpoint, user/seats), right after `require_quota` has
  let the request through and the row exists. There is no accrual step to
  hook for a stock resource: its "usage" is a live ``COUNT(*)``.

**Both entry points swallow every exception.** That is load-bearing, not
defensive habit. `increment_usage` runs inside the `accrue_usage` Celery
task, whose bare ``except`` calls ``self.retry()`` -- so anything raised
here after its ``db.commit()`` would re-run an accrual that already
committed, inflating the counter by one per retry and 402-blocking the org
at a fraction of its real limit. `routers/project.py` has the same shape:
it commits the project before this runs. Notification is bookkeeping
attached to someone else's committed work and must never be able to fail
or repeat it.

Notifies `organization.owner_id` only, not every `Organization.UPDATE`
holder. The full set needs a reverse RBAC lookup ("every user holding this
permission"), which does not exist yet -- building it means a new
pluggable provider (mirroring `QuotaProvider`/`AuthorizationProvider`),
since core code cannot import EE's `Role`/`RolePermission` models. The
owner is a field on `Organization` already, and is exactly the
`Organization.UPDATE` set in community edition; in EE it may miss an Admin
who also holds that permission.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaRegistry, QuotaResource, resource_label
from rhesis.backend.app.services.notification import RenderedNotification, notify
from rhesis.backend.app.services.usage import _STOCK_COUNTERS

logger = logging.getLogger(__name__)

#: Matches the frontend's `WARNING_THRESHOLD` (`constants/quota.ts`). Kept as
#: a separate constant rather than shared -- there is no module both languages
#: import -- so changing one means changing the other.
_APPROACHING_RATIO = 0.8


def notify_flow_crossing(
    db: Session,
    org_id: Optional[str],
    resource: QuotaResource,
    *,
    previous_used: int,
    new_used: int,
) -> None:
    """Notify on a flow resource's threshold crossing. Never raises.

    *previous_used* is a proxy (*new_used* minus the amount just accrued),
    not a value read inside the same transaction as the write. Exact under
    normal traffic; under two concurrent accruals landing on the same
    threshold at the same instant a crossing could double-fire or, rarely,
    be missed. Not worth a race-proof CTE at this platform's scale.
    """
    try:
        if not org_id:
            return
        org = db.query(Organization).filter(Organization.id == org_id).first()
        _notify_crossing(db, org, resource, previous_used=previous_used, new_used=new_used)
    except Exception:
        logger.exception(
            "Failed to notify a %s threshold crossing for org %s", resource.value, org_id
        )


def notify_stock_crossing(
    db: Session, org: Optional[Organization], resource: QuotaResource
) -> None:
    """Count *resource* live and notify if this creation just crossed a
    threshold. Never raises.

    The count is taken here rather than by the caller so it lands inside
    this function's exception guard -- a failing ``COUNT(*)`` must not turn
    an already-committed creation into a 500. Stock resources always move
    by exactly one, so ``new_used - 1`` is the true previous value, not a
    proxy.
    """
    try:
        if org is None:
            return
        counter = _STOCK_COUNTERS.get(resource)
        if counter is None:
            logger.warning("notify_stock_crossing called for non-stock %s", resource.value)
            return
        new_used = counter(db, str(org.id))
        _notify_crossing(db, org, resource, previous_used=new_used - 1, new_used=new_used)
    except Exception:
        logger.exception(
            "Failed to notify a %s threshold crossing for org %s",
            resource.value,
            org.id if org else None,
        )


def _notify_crossing(
    db: Session,
    org: Optional[Organization],
    resource: QuotaResource,
    *,
    previous_used: int,
    new_used: int,
) -> None:
    """Fire at most one notification if this change spans a threshold.

    Compares the *range* against each threshold rather than classifying
    *new_used* alone, so an org that has been sitting past a threshold for
    weeks is not renotified on every subsequent call -- only the change
    whose range actually crosses it fires. `blocked` is checked first and
    returns, so one large jump past both thresholds reports the worse one.

    A resource whose limit is ``0`` never notifies: it is blocked from the
    org's very first request, so there is no transition to report, and the
    banner and inline gates already say so. Unlimited (``limit is None``)
    likewise has nothing to cross.
    """
    if org is None or not org.owner_id:
        return

    policy = QuotaRegistry.get_policy(org)
    limit = policy.limits.get(resource)
    if limit is None:
        return

    # ceiling_for() returns None only for an unlimited limit, already handled.
    ceiling = policy.ceiling_for(limit)
    label = resource_label(resource)
    # Flow resources accrue against a billing period and reset; stock
    # resources are a live count with no period, so the phrasing differs --
    # same split the frontend's quotaCopy() makes.
    period_suffix = "" if resource in _STOCK_COUNTERS else " for this period"

    if ceiling is not None and previous_used < ceiling <= new_used:
        _notify_owner(
            db,
            org,
            event_type=NotificationEventType.Usage.BLOCKED,
            title=f"{label.capitalize()} limit reached",
            body=(
                f"Your organization is at its {label} limit{period_suffix} "
                f"({new_used:,} of {limit:,})."
            ),
        )
        return

    threshold = limit * _APPROACHING_RATIO
    if previous_used < threshold <= new_used:
        percent = round(new_used / limit * 100)
        _notify_owner(
            db,
            org,
            event_type=NotificationEventType.Usage.APPROACHING_LIMIT,
            title=f"{label.capitalize()} approaching limit",
            body=(
                f"Your organization is using {new_used:,} of {limit:,} {label}."
                if resource in _STOCK_COUNTERS
                else f"Your organization has used {percent}% of its {label} for this period."
            ),
        )


def _notify_owner(
    db: Session, org: Organization, *, event_type: str, title: str, body: str
) -> None:
    """Write the notification org-wide (``project_id`` NULL).

    The explicit no-project scope is required, not tidiness: `auto_stamp`
    (`models/scope_events.py`) fills a ``None`` ``project_id`` from the
    session's scope, and the stock-resource callers run inside a
    project-scoped request. Without this the row would be stamped with
    whichever project the acting admin happened to have selected, and
    `auto_filter` plus the RESTRICTIVE ``project_isolation`` RLS policy
    would then hide it from the owner in every *other* project. A quota
    crossing is about the organization, not one project inside it.
    """
    with temporary_project_scope(db, str(org.id), str(org.owner_id), ""):
        notify(
            db,
            event_type=event_type,
            rendered=RenderedNotification(title=title, body=body),
            user_id=str(org.owner_id),
            organization_id=str(org.id),
            project_id=None,
        )
