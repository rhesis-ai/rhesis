"""FastAPI dependencies for feature gating.

Thin adapters that route request-scoped access control through the
central :class:`~rhesis.backend.app.features.FeatureRegistry`. Use
:func:`require_feature` on routes that should 404 when a feature is
unavailable (preventing enumeration) and :func:`has_feature` on routes
that need to branch on availability rather than reject.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.dependencies import get_db_session
from rhesis.backend.app.features import (
    FeatureNameLike,
    FeatureRegistry,
)
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User

# Set on the dependency require_feature returns, so a route's feature can be read back.
_FEATURE_ATTR = "__rhesis_feature__"


def _load_org(user: User, db: Session) -> Organization:
    """Load the organization for *user* within the supplied session.

    The User instance returned by JWT auth is loaded inside a short-lived
    ``get_db()`` context that closes before this dependency runs, so
    accessing ``user.organization`` (a lazy relationship) raises
    ``DetachedInstanceError``. Loading the org explicitly with a live
    session avoids the detach.
    """
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an organization",
        )
    return org


def require_feature(name: FeatureNameLike):
    """Dependency factory: raise 404 if ``name`` is not available.

    Returning 404 (not 403) prevents feature enumeration -- from the
    outside an unlicensed feature is indistinguishable from a non-existent
    route. The dependency resolves the current user's organization and
    returns it so handlers can use it directly.
    """

    def _dep(
        current_user: User = Depends(require_current_user_or_token),
        db: Session = Depends(get_db_session),
    ) -> Organization:
        org = _load_org(current_user, db)
        if not FeatureRegistry.is_available(name, org):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not available",
            )
        return org

    setattr(_dep, _FEATURE_ATTR, str(name))
    return _dep


def feature_for_route(route: object) -> Optional[str]:
    """Return the feature a route is gated on by :func:`require_feature`, or ``None``.

    Walks the whole dependency tree, so a gate declared on the router or on a
    sub-dependency counts too.
    """
    dependant = getattr(route, "dependant", None)
    stack = list(getattr(dependant, "dependencies", None) or [])
    seen: set[int] = set()
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        feature = getattr(dep.call, _FEATURE_ATTR, None)
        if feature is not None:
            return feature
        stack.extend(dep.dependencies)
    return None


def has_feature(name: FeatureNameLike):
    """Dependency factory: resolve to ``bool`` for branching handlers."""

    def _dep(
        current_user: User = Depends(require_current_user_or_token),
        db: Session = Depends(get_db_session),
    ) -> bool:
        org = _load_org(current_user, db)
        return FeatureRegistry.is_available(name, org)

    return _dep


def require_rhesis_key_enabled() -> None:
    """Dependency: raise 404 unless ENABLE_RHESIS_KEY is set.

    Rhesis platform API key endpoints (``/platform``) mount unconditionally
    but must be invisible when the feature is disabled. Returning 404 (not
    403) makes a disabled endpoint indistinguishable from a non-existent
    route from the outside, preventing enumeration -- the same rationale as
    :func:`require_feature`. Unlike ``require_feature`` this gate needs no
    organization, so it is a plain dependency rather than a factory.
    """
    if not get_application_settings().enable_rhesis_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not available",
        )
    return None


__all__ = [
    "feature_for_route",
    "has_feature",
    "require_feature",
    "require_rhesis_key_enabled",
]
