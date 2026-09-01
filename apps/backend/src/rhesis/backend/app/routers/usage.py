"""Usage accounting endpoint.

Exposes :func:`~rhesis.backend.app.services.usage.get_usage_summary` to
the frontend. Read-only -- no enforcement (see the `require_quota`
dependency planned for a later sub-plan).
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.dependencies import get_current_organization, get_tenant_db_session
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.usage import (
    InvalidPeriodError,
    get_usage_history,
    get_usage_summary,
)

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageResourceItem(BaseModel):
    used: int
    limit: int | None
    #: The value of ``used`` at which requests actually start failing --
    #: ``limit`` plus the tier's overage tolerance on a SOFT policy, and
    #: ``limit`` itself on a HARD one. Compare against this, not ``limit``,
    #: to predict a 402; ``limit`` is what a progress bar fills toward.
    ceiling: int | None
    period_start: str
    period_end: str
    kind: str


class PlanInfo(BaseModel):
    """Everything a client needs to render the org's plan, and nothing it
    should have to interpret.

    Deliberately no tier enum on the wire. A client that switches on tier
    names has to ship a release before a new or renamed tier displays
    correctly; one that reads ``name`` plus two booleans does not.
    """

    #: Display label. **Render verbatim** -- do not map, case or append to it.
    #: Composed server-side (see ``services.usage.build_plan``), including the
    #: qualifier a lapsed paid tier carries.
    name: str
    #: Whether this is a paid tier. Describes the *tier*, not the licence, so a
    #: canceled enterprise licence is still ``is_paid=True``.
    is_paid: bool = False
    #: Whether the licence is currently active. ``is_paid`` and ``is_active``
    #: together separate a free org ``(False, False)`` from a lapsed paid one
    #: ``(True, False)`` -- the distinction that decides both the badge styling
    #: and whether an upgrade path is offered.
    is_active: bool = False


class UsageResponse(BaseModel):
    resources: Dict[str, UsageResourceItem] = Field(default_factory=dict)
    #: Machine identifier for the licence edition. Diagnostics and analytics
    #: only -- never for display or for deciding styling. Use ``plan``.
    edition: str
    plan: PlanInfo


class UsageHistoryPoint(BaseModel):
    period_start: str
    used: int


class UsageHistoryResponse(BaseModel):
    resources: Dict[str, List[UsageHistoryPoint]] = Field(default_factory=dict)


@router.get("", response_model=UsageResponse, **capability(Permission.Usage.READ))
def get_usage(
    period: date | None = Query(
        None,
        description=(
            "First day of the month to report; defaults to the current month. "
            "Only affects flow resources -- stock resources (seats, projects, "
            "endpoints) always report today's live count, since they have no "
            "history to look up for a past month."
        ),
    ),
    org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_tenant_db_session),
) -> UsageResponse:
    """Return per-resource usage, limits, and the billing period."""
    try:
        summary = get_usage_summary(db, str(org.id), org, period_start=period)
    except InvalidPeriodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UsageResponse(
        resources={k: UsageResourceItem(**v) for k, v in summary["resources"].items()},
        edition=summary["edition"],
        plan=PlanInfo(**summary["plan"]),
    )


@router.get(
    "/history",
    response_model=UsageHistoryResponse,
    **capability(Permission.Usage.READ),
)
def get_usage_history_endpoint(
    months: int = Query(6, ge=1, le=24, description="Trailing calendar months to include"),
    org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_tenant_db_session),
) -> UsageHistoryResponse:
    """Return monthly usage history for flow resources over the trailing period.

    Stock resources (seats, projects, endpoints) have no history to
    report -- they're live counts, not accrued -- so they're absent from
    the response rather than repeating the same live count at every point.
    """
    history = get_usage_history(db, str(org.id), months)
    return UsageHistoryResponse(
        resources={
            k: [UsageHistoryPoint(**p) for p in points]
            for k, points in history["resources"].items()
        }
    )
