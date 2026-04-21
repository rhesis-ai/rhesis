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

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from rhesis.backend.app.auth.user_utils import require_current_user
from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.models.user import User

router = APIRouter(prefix="/features", tags=["features"])


class LicenseInfo(BaseModel):
    edition: str
    licensed: bool


class FeaturesResponse(BaseModel):
    license: LicenseInfo
    enabled: List[str]


@router.get("", response_model=FeaturesResponse)
def list_features(current_user: User = Depends(require_current_user)) -> FeaturesResponse:
    """Return license info and the set of features enabled for the current user's org."""
    org = current_user.organization
    enabled = [f.name.value for f in FeatureRegistry.enabled_features(org)]
    info = FeatureRegistry.license_info()
    return FeaturesResponse(
        license=LicenseInfo(
            edition=str(info.get("edition", "community")),
            licensed=bool(info.get("licensed", False)),
        ),
        enabled=enabled,
    )
