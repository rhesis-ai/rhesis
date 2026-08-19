"""The single blocking rule quota enforcement uses, wherever it fires.

:func:`check_quota` reads exactly one resource's usage against its policy
and returns a verdict; it never raises. :func:`enforce_quota` wraps it and
raises :class:`QuotaExceededError` when blocked -- the one call both
``auth/quota_gates.py`` (the HTTP dependency) and
``utils/user_model_utils.py`` (the pre-call token gate) use, so a request
blocked at a route and a model resolution blocked inside a Celery task
hit identical logic and produce an identical error shape (see
``error_handlers.py``, which maps :class:`QuotaExceededError` to the 402
response both paths share).

Deliberately not :func:`~rhesis.backend.app.services.usage.get_usage_summary`:
that computes every :class:`QuotaResource`, including three ``COUNT(*)``
queries for stock resources a given check does not care about. A gate that
runs on every execute/generate request, and on every hosted-model call,
should not pay for six resources to answer a question about one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.usage import Usage
from rhesis.backend.app.quota import QuotaRegistry, QuotaResource
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.app.services.usage import (
    _STOCK_COUNTERS,
    FLOW_KIND,
    STOCK_KIND,
    _current_period,
)


@dataclass(frozen=True)
class QuotaVerdict:
    """The outcome of checking one org's usage of one resource.

    :param resource: the resource that was checked.
    :param used: current usage (a live count for stock resources, the
        current billing period's accrued total for flow resources).
    :param limit: the tier's cap for this resource, or ``None`` if unlimited.
    :param allowed: whether the request may proceed.
    :param over_limit: whether *used* has reached *limit*, independent of
        *allowed*. ``over_limit and allowed`` is exactly the soft-overage
        grace band: past the advertised limit but not yet at the hard
        ceiling. ``over_limit`` is always ``False`` when *limit* is ``None``.
    :param kind: ``"flow"`` or ``"stock"`` -- same split as
        :func:`~rhesis.backend.app.services.usage.get_usage_summary`, so a
        402 body can be classified identically to a `GET /usage` row
        without the frontend re-deriving the split.
    :param period_end: ISO date the current billing period ends, so a
        blocked flow resource can be told when it resets without a second
        round trip to `GET /usage`.
    """

    resource: QuotaResource
    used: int
    limit: Optional[int]
    allowed: bool
    over_limit: bool
    kind: str
    period_end: str


class QuotaExceededError(Exception):
    """*resource* is at or past its enforceable ceiling; the request is blocked.

    A domain exception, not an ``HTTPException``: the token gate in
    ``user_model_utils.py`` can run inside a Celery task (metric evaluation
    resolves models there), where there is no HTTP response to raise into.
    Both that gate and the HTTP dependency in ``auth/quota_gates.py`` raise
    this and let it propagate; the global handler registered in ``main.py``
    is what turns it into a 402 when it reaches a request, and the Celery
    task boundary is what turns it into a failed task when it doesn't.

    A caller wrapped by a decorator that catches bare ``Exception`` before
    it reaches that global handler (``@handle_database_exceptions``, at
    least once so far -- see ``routers/user.py:create_user``) cannot rely
    on this propagating cleanly, and must catch it and build the response
    itself via :func:`quota_exceeded_response_body` instead.
    """

    def __init__(self, verdict: QuotaVerdict) -> None:
        self.verdict = verdict
        super().__init__(
            f"Quota exceeded for {verdict.resource.value}: {verdict.used}/{verdict.limit} used"
        )


def quota_exceeded_response_body(verdict: QuotaVerdict) -> dict:
    """Build the JSON body every 402 quota response shares.

    Single source of truth so the shape can't drift between the global
    ``QuotaExceededError`` handler in ``main.py`` and any call site that
    must build the response itself instead of letting the exception
    propagate there (see the note on :class:`QuotaExceededError`).
    """
    resource_display = verdict.resource.value.replace("_", " ")
    is_stock = verdict.resource in _STOCK_COUNTERS
    suffix = "" if is_stock else " for this period"
    return {
        "error": "quota_exceeded",
        "resource": verdict.resource.value,
        "used": verdict.used,
        "limit": verdict.limit,
        "kind": verdict.kind,
        "period_end": verdict.period_end,
        "message": f"You've reached your {resource_display} limit{suffix}.",
    }


def _read_usage(db: Session, org_id: str, resource: QuotaResource) -> int:
    """Read current usage for exactly one resource.

    Stock resources (seats, projects, endpoints) are a live ``COUNT(*)`` via
    the same ``_STOCK_COUNTERS`` map ``get_usage_summary`` uses. Flow
    resources are a single targeted row lookup for the current billing
    period, not the batch-all-resources query ``get_usage_summary`` runs --
    a quota check only ever needs one number.
    """
    counter = _STOCK_COUNTERS.get(resource)
    if counter is not None:
        return counter(db, org_id)

    period_start, _period_end = _current_period()
    # Explicit org_id filter; bypass the ORM auto-filter which may carry a different tenant.
    with bypass_tenant_filter():
        used = (
            db.query(Usage.used)
            .filter(
                Usage.organization_id == org_id,
                Usage.resource == resource.value,
                Usage.period_start == period_start,
            )
            .scalar()
        )
    return used or 0


def check_quota(
    db: Session,
    org_id: str,
    org: Optional[Organization],
    resource: QuotaResource,
) -> QuotaVerdict:
    """Return whether *org_id* may still consume *resource*. Never raises.

    Blocking rule, with ``ceiling = policy.ceiling_for(limit)``:

    - ``limit is None`` -> always allowed (unlimited).
    - ``used < limit`` -> allowed.
    - ``used >= limit``, policy ``HARD`` -> blocked (``ceiling == limit``
      for ``HARD``, so this is really just ``used >= ceiling``).
    - ``limit <= used < ceiling``, policy ``SOFT`` -> allowed, over_limit
      (the grace band).
    - ``used >= ceiling``, policy ``SOFT`` -> blocked.
    """
    policy = QuotaRegistry.get_policy(org)
    limit = policy.limits.get(resource)
    used = _read_usage(db, org_id, resource)
    kind = STOCK_KIND if resource in _STOCK_COUNTERS else FLOW_KIND
    _, period_end = _current_period()

    if limit is None:
        return QuotaVerdict(
            resource=resource,
            used=used,
            limit=None,
            allowed=True,
            over_limit=False,
            kind=kind,
            period_end=period_end.isoformat(),
        )

    ceiling = policy.ceiling_for(limit)
    return QuotaVerdict(
        resource=resource,
        used=used,
        limit=limit,
        allowed=used < ceiling,
        over_limit=used >= limit,
        kind=kind,
        period_end=period_end.isoformat(),
    )


def enforce_quota(
    db: Session,
    org_id: str,
    org: Optional[Organization],
    resource: QuotaResource,
) -> QuotaVerdict:
    """Check *resource* for *org_id* and raise if blocked.

    The shared entry point for both enforcement paths -- see the module
    docstring. Returns the verdict when allowed, so a caller in the soft
    grace band (``verdict.over_limit``) can still act on it (a warning
    response header, say) without a second query.

    :raises QuotaExceededError: if the verdict is not allowed.
    """
    verdict = check_quota(db, org_id, org, resource)
    if not verdict.allowed:
        raise QuotaExceededError(verdict)
    return verdict


__all__ = [
    "QuotaExceededError",
    "QuotaVerdict",
    "check_quota",
    "enforce_quota",
    "quota_exceeded_response_body",
]
