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

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.dependencies import get_current_organization_optional
from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaRegistry, limits_to_wire
from rhesis.backend.app.services.plan import build_plan

router = APIRouter(prefix="/features", tags=["features"])


class LicenseInfo(BaseModel):
    edition: str
    licensed: bool
    #: Whether ``edition`` is a paid tier. A property of the tier, not of the
    #: licence state, so a lapsed paid licence is ``is_paid=True`` with
    #: ``licensed=False`` -- the pair that tells "free tier" apart from "paid
    #: tier, expired".
    #:
    #: Carried here because this response already reports ``edition`` and
    #: ``licensed``; without it, a client holding two of the three facts is
    #: invited to infer the third from the edition *name*
    #: (``edition !== "community"``), which silently misreads any tier added
    #: or renamed later. Never derive paid-ness from the name.
    #:
    #: For *displaying* a plan, use the ``plan`` field below instead: it
    #: carries the composed display label as well, and is what the frontend's
    #: single plan badge renders. These two fields are for gating and
    #: diagnostics.
    is_paid: bool = False


class PlanInfo(BaseModel):
    """Everything a client needs to render the org's plan, and nothing it
    should have to interpret.

    Deliberately no tier enum on the wire. A client that switches on tier
    names has to ship a release before a new or renamed tier displays
    correctly; one that reads ``name`` plus two booleans does not.

    Carried on this endpoint rather than ``GET /usage`` because it costs
    nothing here -- :func:`~rhesis.backend.app.services.plan.build_plan` is a
    pure function of the ``license_info`` this handler already resolves -- and
    because this response is server-seeded in the frontend's protected layout,
    so the plan is present on first paint instead of one round trip late.
    """

    #: Display label. **Render verbatim** -- do not map, case or append to it.
    #: Composed server-side (see ``services.plan.build_plan``), including the
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


class FeaturesResponse(BaseModel):
    license: LicenseInfo
    #: The org's plan, ready to render. See :class:`PlanInfo`.
    plan: PlanInfo
    enabled: List[str]
    warnings: Dict[str, str] = Field(default_factory=dict)
    limits: Dict[str, int | None] = Field(default_factory=dict)
    #: Whether this deployment runs in local/self-hosted mode (BACKEND_ENV=local).
    #: Single source of truth for local-only UI (e.g. the platform key card) --
    #: the frontend derives this from here instead of its own env var so the two
    #: can never drift apart.
    is_local: bool = False
    #: Whether the Rhesis platform API key option is enabled (ENABLE_RHESIS_KEY=true).
    #: Controls the platform key UI and endpoints independently of deployment type.
    rhesis_key_enabled: bool = False


@router.get("", response_model=FeaturesResponse)
def list_features(
    org: Optional[Organization] = Depends(get_current_organization_optional),
) -> FeaturesResponse:
    """Return license info and the set of features enabled for the current user's org.

    Works for users mid-onboarding who have no org yet: returns default-tier
    limits and no enabled features, so the frontend can size the invitation
    form to the tier's seat cap before the org exists.
    """
    enabled = [f.name.value for f in FeatureRegistry.licensed_features(org)] if org else []
    warnings = FeatureRegistry.feature_warnings(org) if org else {}
    info = FeatureRegistry.license_info(org=org)
    limits = limits_to_wire(QuotaRegistry.get_limits(org))
    return FeaturesResponse(
        license=LicenseInfo(
            edition=str(info.get("edition", "community")),
            licensed=bool(info.get("licensed", False)),
            # Defaults to False when a provider omits it: an unknown posture
            # must never present as paid.
            is_paid=bool(info.get("is_paid", False)),
        ),
        # Free: build_plan is pure, over the info dict already resolved above.
        plan=PlanInfo(**build_plan(info)),
        enabled=enabled,
        warnings=warnings,
        limits=limits,
        is_local=get_application_settings().is_local,
        rhesis_key_enabled=get_application_settings().enable_rhesis_key,
    )
