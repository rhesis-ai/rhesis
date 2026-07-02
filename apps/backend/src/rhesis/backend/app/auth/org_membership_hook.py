"""Extension point for default org-role assignment on user↔org association.

When a user is associated with an organization — invited via ``POST /users/``,
re-invited after leaving, or as the creator during onboarding — they must
receive an ``organization_member`` row so the EE
:class:`~rhesis.backend.ee.rbac.provider.PermissionAuthorizationProvider` can
resolve their permissions.  Without it, the EE provider falls through to deny
and the user is 403'd on every protected endpoint the moment RBAC is switched
on for their org.

``organization_member`` is an EE concept, and core must never import EE
(``community-boundary`` CI job).  So core exposes this tiny hook registry and
EE registers a handler in its :func:`~rhesis.backend.ee.bootstrap`.  Core calls
:func:`on_user_org_assigned` from ``crud.create_user`` (and the onboarding /
re-invite paths); when no handler is registered (community build) it is a no-op.

Contract
--------
A handler is ``Callable[[Session, UUID, UUID], None]`` receiving
``(db, user_id, organization_id)``.  It must be idempotent (the same user may be
re-invited), must not commit / rollback the session, and decides the role itself
(Owner for the org creator — ``organization.owner_id == user_id`` — else Member).

Why a list (not a single slot)?
--------------------------------
Mirrors :func:`~rhesis.backend.app.auth.provider_hooks.register_provider_enricher`:
registration is idempotent for the same callable so a bootstrap that runs twice
in a test suite is safe, and the list keeps the door open for a second consumer
without reworking the registry.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Signature for an org-membership handler.
OrgMembershipHandler = Callable[["Session", UUID, UUID], None]

_handlers: List[OrgMembershipHandler] = []


def register_org_membership_handler(handler: OrgMembershipHandler) -> None:
    """Register *handler* to run when a user is assigned to an organization.

    Idempotent: re-registering the same callable is a no-op, so an EE bootstrap
    that runs multiple times across a test suite is safe.
    """
    if handler not in _handlers:
        _handlers.append(handler)
        logger.debug(
            "org-membership handler registered: %s",
            getattr(handler, "__qualname__", repr(handler)),
        )


def on_user_org_assigned(db: "Session", user_id: UUID, organization_id: UUID) -> None:
    """Notify registered handlers that *user_id* now belongs to *organization_id*.

    Called by core from the user-creation / onboarding / re-invite paths after
    the user↔org association is flushed.  No-op when no handler is registered
    (community build) or when *organization_id* is falsy (user not yet in an org).

    A handler raising is logged and re-raised: a failure to seed the default role
    must not silently leave the user lockable-out, it should surface loudly.
    """
    if not organization_id or not _handlers:
        return
    for handler in _handlers:
        handler(db, user_id, organization_id)


def reset_org_membership_handlers() -> None:
    """Clear all registered handlers. For tests only."""
    _handlers.clear()


__all__ = [
    "OrgMembershipHandler",
    "on_user_org_assigned",
    "register_org_membership_handler",
    "reset_org_membership_handlers",
]
