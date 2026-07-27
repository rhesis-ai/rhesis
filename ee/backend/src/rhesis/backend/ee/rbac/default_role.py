"""Default org-role assignment on user↔org association (EE handler).

Registered with core's :func:`~rhesis.backend.app.auth.org_membership_hook`
registry at EE bootstrap.  Core calls the hook from ``crud.create_user`` and the
onboarding / re-invite paths; this handler writes the ``organization_member``
row that the :class:`~rhesis.backend.ee.rbac.provider.PermissionAuthorizationProvider`
needs so the user is not denied everywhere once RBAC is enabled for their org.

Role choice (matches the SP8 backfill mapping):

- the **org creator** (``organization.owner_id == user_id``) → **Owner**,
- everyone else → **Member** (deliberately *not* Admin — Admin would grant new
  invitees write access to org settings).

Rows are written on every user↔org association regardless of whether RBAC is
currently licensed for the org.  While RBAC is off the EE provider is inactive
and the row is dormant; once RBAC activates the user is not locked out.  The
SP8 backfill migration (371c3c3cd787) and its catch-up (f8e9a0b1c2d4) cover
orgs that existed before this handler could run.  Idempotent — re-invites and
double-fires are safe.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _sync_project_roles_from_org_role(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    role_id: UUID,
) -> None:
    """Copy *role_id* into project memberships that have no explicit project role.

    Idempotent — never overwrites an existing ``project_membership.role_id``.
    """
    from rhesis.backend.app.models.project_membership import ProjectMembership

    db.query(ProjectMembership).filter_by(
        organization_id=organization_id,
        user_id=user_id,
    ).filter(ProjectMembership.role_id.is_(None)).update(
        {ProjectMembership.role_id: role_id},
        synchronize_session=False,
    )
    db.flush()


def assign_default_org_role(db: Session, user_id: UUID, organization_id: UUID) -> None:
    """Insert the default ``organization_member`` row for *user_id* in *organization_id*.

    No-op when a row already exists or when the relevant built-in role is missing.
    Never commits/rolls back.
    """
    from rhesis.backend.app.models.organization import Organization
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import OrganizationMember, Role

    with bypass_tenant_filter():
        org = db.query(Organization).filter_by(id=organization_id).first()
    if org is None:
        return

    # Idempotent: never overwrite an existing assignment (e.g. an Owner who is
    # re-invited must keep Owner, not be downgraded to Member).
    existing = (
        db.query(OrganizationMember)
        .filter_by(organization_id=organization_id, user_id=user_id)
        .first()
    )
    if existing is not None:
        if existing.role_id is not None:
            _sync_project_roles_from_org_role(
                db, user_id, organization_id, existing.role_id
            )
        return

    role_name = "Owner" if str(org.owner_id) == str(user_id) else "Member"
    with bypass_tenant_filter():
        role = (
            db.query(Role)
            .filter_by(name=role_name, is_built_in=True, organization_id=None)
            .first()
        )
    if role is None:
        logger.warning(
            "default org-role: built-in role %r not found; cannot seed "
            "organization_member for user %s org %s",
            role_name,
            user_id,
            organization_id,
        )
        return

    db.add(
        OrganizationMember(
            organization_id=organization_id,
            user_id=user_id,
            role_id=role.id,
        )
    )
    db.flush()
    _sync_project_roles_from_org_role(db, user_id, organization_id, role.id)

    # Revocation/grant must take effect immediately for this user.
    try:
        from rhesis.backend.app.services.permission_cache import get_permission_cache

        get_permission_cache().bust_user(user_id, organization_id)
    except Exception as exc:  # non-fatal
        logger.warning(
            "default org-role: permission cache bust failed for user %s org %s: %s",
            user_id,
            organization_id,
            exc,
        )

    logger.info(
        "default org-role: assigned %s to user %s in org %s",
        role_name,
        user_id,
        organization_id,
    )


__all__ = ["assign_default_org_role"]
