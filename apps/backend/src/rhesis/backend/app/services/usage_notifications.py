"""Threshold-crossing notifications for quota usage.

Turns a change in a resource's usage into an in-app notification for the
org owner when the change just crossed 80% of the resource's `limit`, or
its `ceiling` -- not on every call once an org is already past a
threshold, only on the transition. Called from two places:

- `services/usage.py:increment_usage`, for flow resources (test executions,
  test generation, tracing spans, model tokens) -- the accrual write itself
  is the natural point to compare before/after.
- The three stock-resource creation routes (project, endpoint, user/seats)
  right after `require_quota` has let the request through and the row is
  created -- there is no accrual step for a stock resource to hook into,
  since its "usage" is a live `COUNT(*)`, not a counter.

Notifies only `organization.owner_id`, not every `Organization.UPDATE`
holder. The full set requires a reverse RBAC lookup ("every user who holds
this permission"), which doesn't exist yet -- building it means a new
pluggable provider (mirroring `QuotaProvider`/`AuthorizationProvider`),
since core code cannot import EE's `Role`/`RolePermission` models directly.
The owner is a zero-cost field on `Organization` already, and is exactly
the `Organization.UPDATE` set in community edition; in EE it may miss an
Admin who also holds that permission, but the owner still gets notified.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaRegistry, QuotaResource
from rhesis.backend.app.services.notification import RenderedNotification, notify

logger = logging.getLogger(__name__)

#: Matches the frontend's `WARNING_THRESHOLD` (`constants/quota.ts`) -- kept
#: as a separate constant, not a shared one, since there is no shared module
#: between the two languages; if one changes, change both.
_APPROACHING_RATIO = 0.8


def _resource_label(resource: QuotaResource) -> str:
    return resource.value.replace("_", " ")


def check_and_notify_threshold_crossing(
    db: Session,
    org: Optional[Organization],
    resource: QuotaResource,
    *,
    previous_used: int,
    new_used: int,
) -> None:
    """Notify the org owner if this change just crossed 80% of `limit` or `ceiling`.

    Compares `previous_used`/`new_used` against each threshold rather than
    just classifying `new_used`'s zone, so an org that has been sitting
    past a threshold for weeks isn't renotified on every subsequent call --
    only the call whose range actually spans the threshold fires.

    `previous_used` is a proxy (`new_used` minus the amount just added),
    not a value read from the database inside the same transaction as the
    write. That is exact under normal traffic; under two concurrent writes
    landing on the same threshold at the same instant, one crossing could
    double-fire or (rarely) get missed. Not worth a race-proof CTE for how
    few orgs are on this platform -- see the "reduce safety margin"
    guidance in project memory.

    No-ops silently on any failure (notification is not the operation this
    call is attached to) or if `org` has no id to notify, or the resource
    is unlimited for this org.
    """
    if org is None or not org.owner_id:
        return

    policy = QuotaRegistry.get_policy(org)
    limit = policy.limits.get(resource)
    if limit is None:
        return

    ceiling = policy.ceiling_for(limit)
    label = _resource_label(resource)

    try:
        if ceiling is not None and previous_used < ceiling <= new_used:
            _notify_owner(
                db,
                org,
                event_type=NotificationEventType.Usage.BLOCKED,
                title=f"{label.title()} limit reached",
                body=f"Your organization is at its {label} limit ({new_used} of {limit}).",
            )
            return

        threshold = limit * _APPROACHING_RATIO
        if previous_used < threshold <= new_used:
            _notify_owner(
                db,
                org,
                event_type=NotificationEventType.Usage.APPROACHING_LIMIT,
                title=f"{label.title()} approaching limit",
                body=f"Your organization is using {new_used} of {limit} {label}.",
            )
    except Exception:
        logger.exception(
            "Failed to notify org %s owner of a %s threshold crossing", org.id, resource.value
        )


def _notify_owner(
    db: Session, org: Organization, *, event_type: str, title: str, body: str
) -> None:
    notify(
        db,
        event_type=event_type,
        rendered=RenderedNotification(title=title, body=body),
        user_id=str(org.owner_id),
        organization_id=str(org.id),
        project_id=None,
    )
