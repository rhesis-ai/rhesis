"""Shared org-owner check used by CRUD and RBAC layers.

Determines whether a user is an organization owner. In the community tier this
is ``organization.owner_id == user_id``. EE extends it via
:func:`register_org_owner_checker` to also consult ``organization_member`` roles,
so multiple users can hold Owner-level access.

The result is memoized on ``db.info`` for the life of the request (the same
session-local cache the RBAC layer uses) so repeated calls within a single
request never re-query.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

OrgOwnerChecker = Callable[["Session", UUID, UUID], bool]

_extra_checkers: List[OrgOwnerChecker] = []


def register_org_owner_checker(checker: OrgOwnerChecker) -> None:
    """Register an additional org-owner predicate (EE multi-owner check).

    Idempotent: re-registering the same callable is a no-op.
    """
    if checker not in _extra_checkers:
        _extra_checkers.append(checker)


def reset_org_owner_checkers() -> None:
    """Clear all registered checkers. For tests only."""
    _extra_checkers.clear()


def is_org_owner(db: "Session", user_id: UUID | str, organization_id: UUID | str) -> bool:
    """Return True if *user_id* is an owner of *organization_id*.

    Checks ``organization.owner_id`` (community) plus any registered EE
    checkers.  Memoized on ``db.info`` for the request lifetime.
    """
    cache = db.info.setdefault("_is_org_owner_cache", {})
    key = (str(user_id), str(organization_id))
    if key in cache:
        return cache[key]

    result = _check_org_owner(db, user_id, organization_id)
    cache[key] = result
    return result


def _check_org_owner(db: "Session", user_id: UUID | str, organization_id: UUID | str) -> bool:
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
                "org-owner checker %s raised (non-fatal)",
                getattr(checker, "__qualname__", repr(checker)),
                exc_info=True,
            )

    return False


__all__ = [
    "OrgOwnerChecker",
    "is_org_owner",
    "register_org_owner_checker",
    "reset_org_owner_checkers",
]
