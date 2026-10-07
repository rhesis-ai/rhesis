"""CRUD operations for roles, role permissions and organization members.

The routers and ``default_role`` keep the checks (escalation, last-owner, cache
busting); the rows they write are written here. Nothing here commits.
"""

from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.utils.crud_utils import bulk_delete, bulk_update
from rhesis.backend.ee.rbac.models import OrganizationMember, Role, RolePermission


def create_role(
    db: Session,
    *,
    name: str,
    display_name: str,
    description: Optional[str],
    scope: str,
    level: int,
    organization_id: UUID,
    permission_ids: Iterable[UUID],
) -> Role:
    """Insert a custom role with its permissions, flushed and refreshed."""
    role = Role(
        name=name,
        display_name=display_name,
        description=description,
        scope=scope,
        level=level,
        is_built_in=False,
        organization_id=organization_id,
    )
    db.add(role)
    db.flush()
    db.add_all(RolePermission(role_id=role.id, permission_id=pid) for pid in permission_ids)
    db.flush()
    db.refresh(role)
    return role


def replace_role_permissions(db: Session, role_id: UUID, permission_ids: Iterable[UUID]) -> None:
    """Replace every permission of a role with ``permission_ids``."""
    bulk_delete(db, RolePermission, [RolePermission.role_id == role_id])
    db.add_all(RolePermission(role_id=role_id, permission_id=pid) for pid in permission_ids)


def unassign_role(db: Session, role_id: UUID, organization_id: UUID, none_role_id: UUID) -> None:
    """Move every holder off a role that is about to be deleted.

    Org members keep a role (``role_id`` is NOT NULL), so they get the built-in
    None role; project members fall back to their inherited org role.
    """
    bulk_update(
        db,
        OrganizationMember,
        [
            OrganizationMember.role_id == role_id,
            OrganizationMember.organization_id == organization_id,
        ],
        {OrganizationMember.role_id: none_role_id},
        synchronize_session=False,
    )
    bulk_update(
        db,
        ProjectMembership,
        [
            ProjectMembership.role_id == role_id,
            ProjectMembership.organization_id == organization_id,
        ],
        {ProjectMembership.role_id: None},
        synchronize_session=False,
    )


def set_org_member_role(
    db: Session,
    member: Optional[OrganizationMember],
    *,
    organization_id: UUID,
    user_id: UUID,
    role_id: UUID,
) -> OrganizationMember:
    """Set a user's org role, inserting the member row if there is none."""
    if member is None:
        member = OrganizationMember(
            organization_id=organization_id, user_id=user_id, role_id=role_id
        )
        db.add(member)
    else:
        member.role_id = role_id
    db.flush()
    db.refresh(member)
    return member


def add_org_member(
    db: Session, organization_id: UUID, user_id: UUID, role_id: UUID
) -> OrganizationMember:
    """Insert an org member row and flush."""
    member = OrganizationMember(organization_id=organization_id, user_id=user_id, role_id=role_id)
    db.add(member)
    db.flush()
    return member


def delete_org_member(db: Session, member: OrganizationMember) -> None:
    db.delete(member)
    db.flush()


def inherit_org_role_in_projects(
    db: Session, user_id: UUID, organization_id: UUID, role_id: UUID
) -> List[UUID]:
    """Copy ``role_id`` into the user's project memberships that have no role of their own.

    Never overwrites an explicit project role. Returns the memberships changed.
    """
    ids = bulk_update(
        db,
        ProjectMembership,
        [
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.user_id == user_id,
            ProjectMembership.role_id.is_(None),
        ],
        {ProjectMembership.role_id: role_id},
        synchronize_session=False,
    )
    db.flush()
    return ids
