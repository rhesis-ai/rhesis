"""Usage accounting endpoint.

Exposes :func:`~rhesis.backend.app.services.usage.get_usage_summary` to
the frontend. Read-only -- no enforcement (see the `require_quota`
dependency planned for a later sub-plan).
"""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_current_organization, get_tenant_db_session
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.usage import get_usage_history, get_usage_summary

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageResourceItem(BaseModel):
    used: int
    limit: int | None
    period_start: str
    period_end: str
    kind: str


class UsageResponse(BaseModel):
    resources: Dict[str, UsageResourceItem] = Field(default_factory=dict)
    edition: str


class UsageHistoryPoint(BaseModel):
    period_start: str
    used: int


class UsageHistoryResponse(BaseModel):
    resources: Dict[str, List[UsageHistoryPoint]] = Field(default_factory=dict)


@router.get("", response_model=UsageResponse)
def get_usage(
    org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_tenant_db_session),
) -> UsageResponse:
    """Return per-resource usage, limits, and the current billing period."""
    summary = get_usage_summary(db, str(org.id), org)
    return UsageResponse(
        resources={k: UsageResourceItem(**v) for k, v in summary["resources"].items()},
        edition=summary["edition"],
    )


@router.get("/history", response_model=UsageHistoryResponse)
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
