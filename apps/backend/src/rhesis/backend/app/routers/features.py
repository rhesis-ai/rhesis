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

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from rhesis.backend.app.dependencies import get_current_organization
from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaRegistry, limits_to_wire

router = APIRouter(prefix="/features", tags=["features"])


class LicenseInfo(BaseModel):
    edition: str
    licensed: bool


class FeaturesResponse(BaseModel):
    license: LicenseInfo
    enabled: List[str]
    warnings: Dict[str, str] = Field(default_factory=dict)
    limits: Dict[str, int | None] = Field(default_factory=dict)


@router.get("", response_model=FeaturesResponse)
def list_features(
    org: Organization = Depends(get_current_organization),
) -> FeaturesResponse:
    """Return license info and the set of features enabled for the current user's org."""
    enabled = [f.name.value for f in FeatureRegistry.licensed_features(org)]
    warnings = FeatureRegistry.feature_warnings(org)
    info = FeatureRegistry.license_info(org=org)
    limits = limits_to_wire(QuotaRegistry.get_limits(org))
    return FeaturesResponse(
        license=LicenseInfo(
            edition=str(info.get("edition", "community")),
            licensed=bool(info.get("licensed", False)),
        ),
        enabled=enabled,
        warnings=warnings,
        limits=limits,
    )
