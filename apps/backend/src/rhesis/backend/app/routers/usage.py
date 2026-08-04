"""Usage accounting endpoint.

Exposes :func:`~rhesis.backend.app.services.usage.get_usage_summary` to
the frontend. Read-only -- no enforcement (see the `require_quota`
dependency planned for a later sub-plan).
"""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_current_organization, get_tenant_db_session
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.usage import get_usage_summary

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
