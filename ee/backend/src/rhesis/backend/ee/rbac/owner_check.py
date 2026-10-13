"""EE org-wide project access checker.

Registered with core's :func:`~rhesis.backend.app.auth.org_project_access` at EE
bootstrap.  Extends the community single-``owner_id`` check by querying
``organization_member`` for users whose role level is at least
``ORG_WIDE_ACCESS_LEVEL`` (Owner, Admin, Auditor), matching the EE RBAC provider.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.ee.rbac.models import ORG_WIDE_ACCESS_LEVEL, OrganizationMember, Role


def has_ee_org_wide_project_access(
    db: Session, user_id: UUID | str, organization_id: UUID | str
) -> bool:
    """Return True if *user_id* holds an Auditor-or-above role in *organization_id*."""
    with bypass_tenant_filter():
        return (
            db.query(OrganizationMember)
            .join(Role, OrganizationMember.role_id == Role.id)
            .filter(
                OrganizationMember.organization_id == str(organization_id),
                OrganizationMember.user_id == str(user_id),
                Role.level >= ORG_WIDE_ACCESS_LEVEL,
            )
            .first()
            is not None
        )


__all__ = ["has_ee_org_wide_project_access"]
