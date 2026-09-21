"""EE org-owner checker for the multi-owner case.

Registered with core's :func:`~rhesis.backend.app.auth.org_owner_check` at EE
bootstrap.  Extends the community single-``owner_id`` check by querying
``organization_member`` for users whose role level is >= 100 (Owner).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_LEVELS, OrganizationMember, Role

_OWNER_LEVEL = BUILT_IN_ROLE_LEVELS["Owner"]


def is_ee_org_owner(db: Session, user_id: UUID | str, organization_id: UUID | str) -> bool:
    """Return True if *user_id* holds an Owner-level role in *organization_id*."""
    with bypass_tenant_filter():
        return (
            db.query(OrganizationMember)
            .join(Role, OrganizationMember.role_id == Role.id)
            .filter(
                OrganizationMember.organization_id == str(organization_id),
                OrganizationMember.user_id == str(user_id),
                Role.level >= _OWNER_LEVEL,
            )
            .first()
            is not None
        )


__all__ = ["is_ee_org_owner"]
