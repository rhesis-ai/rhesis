"""Feature catalog endpoints.

Exposes :class:`~rhesis.backend.app.features.FeatureRegistry` state to
the frontend. The single ``GET /features`` endpoint returns the license
info and the set of features enabled for the current user's org, which
the frontend's ``FeaturesProvider`` consumes to drive conditional UI.

Feature names are returned as strings (the raw value of
:class:`~rhesis.backend.app.features.FeatureName` members), keeping
the wire format stable independent of Python enum evolution.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.models.organization import Organization

router = APIRouter(prefix="/features", tags=["features"])


class LicenseInfo(BaseModel):
    edition: str
    licensed: bool


class FeaturesResponse(BaseModel):
    license: LicenseInfo
    enabled: List[str]


@router.get("", response_model=FeaturesResponse)
def list_features(
    tenant_context: tuple = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db_session),
) -> FeaturesResponse:
    """Return license info and the set of features enabled for the current user's org.

    Both dependencies resolve through the same ``require_current_user_or_token``
    call (FastAPI deduplicates it). ``tenant_context`` provides the
    authenticated organization ID so we never accept user-supplied input.
    """
    organization_id, _user_id = tenant_context
    if not organization_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    org = db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Organization not found",
        )
    enabled = [f.name.value for f in FeatureRegistry.enabled_features(org)]
    info = FeatureRegistry.license_info()
    return FeaturesResponse(
        license=LicenseInfo(
            edition=str(info.get("edition", "community")),
            licensed=bool(info.get("licensed", False)),
        ),
        enabled=enabled,
    )
