"""FastAPI dependencies for feature gating.

Thin adapters that route request-scoped access control through the
central :class:`~rhesis.backend.app.features.FeatureRegistry`. Use
:func:`require_feature` on routes that should 404 when a feature is
unavailable (preventing enumeration) and :func:`has_feature` on routes
that need to branch on availability rather than reject.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from rhesis.backend.app.auth.user_utils import require_current_user
from rhesis.backend.app.features import (
    FeatureNameLike,
    FeatureRegistry,
)
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User


def require_feature(name: FeatureNameLike):
    """Dependency factory: raise 404 if ``name`` is not available.

    Returning 404 (not 403) prevents feature enumeration -- from the
    outside an unlicensed feature is indistinguishable from a non-existent
    route. The dependency resolves the current user's organization and
    returns it so handlers can use it directly.
    """

    def _dep(current_user: User = Depends(require_current_user)) -> Organization:
        org: Organization = current_user.organization  # type: ignore[assignment]
        if not FeatureRegistry.is_available(name, org):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not available",
            )
        return org

    return _dep


def has_feature(name: FeatureNameLike):
    """Dependency factory: resolve to ``bool`` for branching handlers."""

    def _dep(current_user: User = Depends(require_current_user)) -> bool:
        org: Organization = current_user.organization  # type: ignore[assignment]
        return FeatureRegistry.is_available(name, org)

    return _dep


__all__ = ["has_feature", "require_feature"]
