"""Org-wide project access check used by CRUD and connector layers.

Determines whether a user has implicit access to *all* projects in an
organization, bypassing the ``project_membership`` filter.  In the community
tier this means ``organization.owner_id == user_id``.  EE extends it via
:func:`register_org_access_checker` to also consult ``organization_member``
roles, so org admins and owners both qualify.

The result is memoized on ``db.info`` for the life of the request (the same
session-local cache pattern the RBAC layer uses) so repeated calls within a
single request never re-query.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

OrgAccessChecker = Callable[["Session", UUID, UUID], bool]

_extra_checkers: List[OrgAccessChecker] = []


def register_org_access_checker(checker: OrgAccessChecker) -> None:
    """Register an additional org-access predicate (EE admin/owner check).

    Idempotent: re-registering the same callable is a no-op.
    """
    if checker not in _extra_checkers:
        _extra_checkers.append(checker)


def reset_org_access_checkers() -> None:
    """Clear all registered checkers. For tests only."""
    _extra_checkers.clear()


def has_org_wide_project_access(
    db: "Session", user_id: UUID | str, organization_id: UUID | str
) -> bool:
    """Return True if *user_id* has implicit access to all projects in *organization_id*.

    Community: ``organization.owner_id``.  EE: any role with level >= Admin (80).
    Memoized on ``db.info`` for the request lifetime.
    """
    cache = db.info.setdefault("_org_wide_project_access_cache", {})
    key = (str(user_id), str(organization_id))
    if key in cache:
        return cache[key]

    result = _check(db, user_id, organization_id)
    cache[key] = result
    return result


def _check(db: "Session", user_id: UUID | str, organization_id: UUID | str) -> bool:
    from rhesis.backend.app.models.organization import Organization

    org = db.query(Organization).filter_by(id=organization_id).first()
    if org is not None and org.owner_id is not None and str(org.owner_id) == str(user_id):
        return True

    for checker in _extra_checkers:
        try:
            if checker(db, user_id, organization_id):
                return True
        except Exception:
            logger.warning(
                "org-access checker %s raised (non-fatal)",
                getattr(checker, "__qualname__", repr(checker)),
                exc_info=True,
            )

    return False


__all__ = [
    "OrgAccessChecker",
    "has_org_wide_project_access",
    "register_org_access_checker",
    "reset_org_access_checkers",
]
