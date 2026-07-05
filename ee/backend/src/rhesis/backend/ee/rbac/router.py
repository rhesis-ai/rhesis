"""EE RBAC role and assignment APIs — SP8.

All endpoints are gated by ``require_feature(FeatureName.RBAC)`` which returns
404 when RBAC is not licensed, preventing feature enumeration.

Endpoints
---------
Role catalog:
  GET  /roles                          — list roles (built-in + org custom)
  GET  /roles/{role_id}                — get a single role with its permissions
  POST /roles                          — create a custom role (escalation-guarded)
  PUT  /roles/{role_id}                — update a custom role (escalation-guarded)
  DELETE /roles/{role_id}              — delete a custom role

Org-level role assignment:
  GET    /organization-members         — list org-level role assignments
  PUT    /organization-members/{user_id}/role   — assign org role
  DELETE /organization-members/{user_id}        — remove org membership row

Project-level role assignment:
  PUT    /projects/{project_id}/members/{user_id}/role  — assign project role

Privilege-escalation guard (load-bearing, plan §2.3):
  A principal may only create or assign a role whose permission set is a
  subset of their own effective permissions, AND may only grant a role whose
  level is ≤ their own level.  Both checks fire on every role create/update/
  assign operation.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.feature_gates import require_feature
from rhesis.backend.app.auth.principal import resolve_principal
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.models.user import User
from rhesis.backend.ee.rbac.schemas import (
    OrgMemberRead,
    OrgRoleAssign,
    ProjectMemberRoleAssign,
    ProjectMemberRoleRead,
    RoleCreate,
    RoleRead,
    RoleUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rbac",
    tags=["rbac"],
    responses={404: {"description": "Not found"}},
)

_RBAC_DEP = Depends(require_feature(FeatureName.RBAC))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_role(role_id: uuid.UUID, db: Session):
    """Load a role bypassing the tenant filter (needed for built-in NULL-org roles)."""
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import Role

    with bypass_tenant_filter():
        return db.query(Role).filter_by(id=role_id).first()


def _get_role_or_404(role_id: uuid.UUID, db: Session):
    """Load a role visible to the current tenant scope, or raise 404."""
    role = _load_role(role_id, db)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def _role_permission_names(role_id: uuid.UUID, db: Session) -> list[str]:
    """Return active permission name strings for *role_id*."""
    from rhesis.backend.ee.rbac.models import Permission, RolePermission

    return [
        row[0]
        for row in db.query(Permission.name)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .filter(RolePermission.role_id == role_id, Permission.is_retired.is_(False))
        .all()
    ]


def _role_permission_names_resolved(role, db: Session) -> list[str]:
    """Return effective permission names for *role*, handling built-ins correctly.

    Built-in roles have no ``role_permission`` rows — their permissions are
    computed from code via ``permissions_for_built_in_role``.  Using this
    resolver in the escalation guard ensures a Member-level actor cannot silently
    skip the permissions check when assigning a built-in (whose DB rows return []).
    """
    if role.is_built_in:
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        return list(permissions_for_built_in_role(role.name, get_all_capabilities()))
    return _role_permission_names(role.id, db)


def _get_actor_level(principal, project_id, db: Session) -> int:
    """Return the privilege level of the actor (0 when RBAC is off or no role)."""
    from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

    role = PermissionAuthorizationProvider().resolve_effective_role(principal, project_id, db)
    return role.level if role is not None else 0


def _get_actor_permissions(principal, project_id, db: Session) -> set[str]:
    """Return the full set of active permission names for the actor at *project_id* scope."""
    from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

    return PermissionAuthorizationProvider().get_effective_permissions(
        principal, project_id=project_id, db=db
    )


def _resolve_permission_ids(permission_names: list[str], db: Session) -> list[uuid.UUID]:
    """Map capability strings to Permission PKs. Raises 422 on unknown names."""
    from rhesis.backend.ee.rbac.models import Permission

    if not permission_names:
        return []

    rows = (
        db.query(Permission)
        .filter(
            Permission.name.in_(permission_names),
            Permission.is_retired.is_(False),
        )
        .all()
    )
    found = {r.name for r in rows}
    unknown = set(permission_names) - found
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown or retired permission names: {sorted(unknown)}",
        )
    return [r.id for r in rows]


def _check_escalation(
    permission_names: list[str],
    role_level: int,
    actor_permissions: set[str],
    actor_level: int,
) -> None:
    """Raise 403 when the requested role would exceed the actor's authority.

    Two guards (plan §2.3):
    1. Requested permission set must be ⊆ actor's permissions.
    2. Role level must be ≤ actor's level.
    """
    over_grant = set(permission_names) - actor_permissions
    if over_grant:
        raise HTTPException(
            status_code=403,
            detail=(
                "Privilege escalation denied: the role includes permissions you "
                f"do not hold: {sorted(over_grant)}"
            ),
        )
    if role_level > actor_level:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Privilege escalation denied: cannot grant a role at level "
                f"{role_level} (your level: {actor_level})"
            ),
        )


def check_project_role_assignment(
    db: Session, actor: User, role_id: uuid.UUID, project_id: uuid.UUID
):
    """Escalation guard for granting *role_id* on *project_id* to a member.

    Shared by the EE ``assign_project_role`` endpoint and the community
    ``add_project_member`` validator hook so both paths enforce the identical
    rule.  Raises 404 (unknown role), 422 (None role at project tier), or 403
    (escalation) on rejection; returns the resolved ``Role`` so callers can
    reuse it without a second load.
    """
    principal = resolve_principal(actor)
    # Both halves of the escalation guard use the project scope for consistency.
    actor_permissions = _get_actor_permissions(principal, project_id=project_id, db=db)
    actor_level = _get_actor_level(principal, project_id=project_id, db=db)

    target_role = _get_role_or_404(role_id, db)

    # One-directional scope gate (K8s ClusterRole model):
    # - Org/built-in roles bind "down" to the project tier.  Owner (level 100)
    #   IS now permitted at the project tier so a project creator or lead can
    #   be designated as the project owner independently of the org owner.
    #   Only None (level 0, explicit revocation) is blocked — it has no useful
    #   meaning as a project assignment.  This matches isAssignableProjectRole.
    # - Project-only custom roles (scope=project) are accepted as before.
    # - The org-tier gate in assign_org_role stays strict: project-only roles
    #   cannot be promoted org-wide.
    if target_role.is_built_in and target_role.level == 0:
        raise HTTPException(
            status_code=422,
            detail="The None role cannot be assigned at the project tier",
        )

    new_perm_names = _role_permission_names_resolved(target_role, db)
    _check_escalation(new_perm_names, target_role.level, actor_permissions, actor_level)
    return target_role


def _bust(user_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Bust the permission cache for *user_id* within *org_id* (non-fatal)."""
    try:
        from rhesis.backend.app.services.permission_cache import get_permission_cache

        get_permission_cache().bust_user(user_id, org_id)
    except Exception as exc:
        logger.warning(
            "permission cache bust failed for user %s org %s (non-fatal): %s",
            user_id,
            org_id,
            exc,
        )


def _bust_role_holders(role_id: uuid.UUID, org_id: uuid.UUID, db: Session) -> None:
    """Bust permission cache for every user currently holding *role_id* in *org_id*.

    Called on update_role / delete_role because a permission-set change affects
    every holder, not just the actor.
    """
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.ee.rbac.models import OrganizationMember

    org_holders = (
        db.query(OrganizationMember.user_id)
        .filter_by(role_id=role_id, organization_id=org_id)
        .all()
    )
    for (uid,) in org_holders:
        _bust(uid, org_id)

    project_holders = (
        db.query(ProjectMembership.user_id)
        .filter_by(role_id=role_id, organization_id=org_id)
        .distinct()
        .all()
    )
    for (uid,) in project_holders:
        _bust(uid, org_id)


def _is_last_owner(member, org_id: uuid.UUID, db: Session) -> bool:
    """Return True when *member* is the sole Owner in *org_id*."""
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import OrganizationMember, Role

    with bypass_tenant_filter():
        owner_role = db.query(Role).filter_by(name="Owner", is_built_in=True).first()
    if owner_role is None or member.role_id != owner_role.id:
        return False
    owner_count = (
        db.query(OrganizationMember)
        .filter_by(organization_id=org_id, role_id=owner_role.id)
        .count()
    )
    return owner_count <= 1


def _member_counts_for_roles(
    role_ids: list[uuid.UUID], org_id: uuid.UUID, db: Session
) -> dict[uuid.UUID, int]:
    """Count distinct users holding each role in *role_ids* within *org_id*.

    One grouped query over the union of org-level (``organization_member``) and
    project-level (``project_membership``) assignments — the ``UNION`` dedups
    ``(role_id, user_id)`` pairs so a user holding the same role at both tiers
    (or on several projects) is counted once per role.  Returns ``{role_id: count}``
    with roles that have no holders omitted (callers default to 0).
    """
    from sqlalchemy import func, select, union

    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.ee.rbac.models import OrganizationMember

    if not role_ids:
        return {}

    org_q = select(
        OrganizationMember.role_id.label("role_id"),
        OrganizationMember.user_id.label("user_id"),
    ).where(
        OrganizationMember.role_id.in_(role_ids),
        OrganizationMember.organization_id == org_id,
    )
    proj_q = select(
        ProjectMembership.role_id.label("role_id"),
        ProjectMembership.user_id.label("user_id"),
    ).where(
        ProjectMembership.role_id.in_(role_ids),
        ProjectMembership.organization_id == org_id,
    )
    unioned = union(org_q, proj_q).subquery()
    rows = db.execute(
        select(unioned.c.role_id, func.count().label("cnt")).group_by(unioned.c.role_id)
    ).all()
    return {row.role_id: row.cnt for row in rows}


def _role_to_read(role, db: Session, member_count: int = 0) -> RoleRead:
    """Serialize a Role ORM object to RoleRead, including permission list.

    Built-in roles have no ``role_permission`` rows — their permissions are
    computed dynamically from ``permissions_for_built_in_role``.  Custom roles
    are resolved from the join table as normal.  *member_count* is supplied by
    the caller (precomputed in bulk for list views) to avoid an N+1.
    """
    from rhesis.backend.app.auth.capabilities import get_all_capabilities
    from rhesis.backend.ee.rbac.models import Permission, RolePermission, permissions_for_built_in_role
    from rhesis.backend.ee.rbac.schemas import PermissionRead

    if role.is_built_in:
        perm_names = permissions_for_built_in_role(role.name, get_all_capabilities())
        perms = (
            db.query(Permission)
            .filter(
                Permission.name.in_(perm_names),
                Permission.is_retired.is_(False),
            )
            .all()
        )
    else:
        perms = (
            db.query(Permission)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .filter(
                RolePermission.role_id == role.id,
                Permission.is_retired.is_(False),
            )
            .all()
        )

    return RoleRead(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        scope=role.scope,
        level=role.level,
        is_built_in=role.is_built_in,
        organization_id=role.organization_id,
        permissions=[PermissionRead.model_validate(p) for p in perms],
        member_count=member_count,
    )


# ---------------------------------------------------------------------------
# Role catalog endpoints
# ---------------------------------------------------------------------------


@router.get("/roles", response_model=list[RoleRead], **capability(Permission.Role.READ))
def list_roles(
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """List all roles visible to the current org (built-in + org custom)."""
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import Role

    with bypass_tenant_filter():
        roles = (
            db.query(Role)
            .filter(
                (Role.organization_id == current_user.organization_id)
                | Role.organization_id.is_(None)
            )
            .all()
        )

    counts = _member_counts_for_roles([r.id for r in roles], current_user.organization_id, db)
    return [_role_to_read(r, db, counts.get(r.id, 0)) for r in roles]


@router.get("/roles/{role_id}", response_model=RoleRead, **capability(Permission.Role.READ))
def get_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """Return a single role with its permission list."""
    role = _get_role_or_404(role_id, db)
    # Restrict: must be built-in or owned by the current org.
    if role.organization_id is not None and role.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Role not found")
    counts = _member_counts_for_roles([role.id], current_user.organization_id, db)
    return _role_to_read(role, db, counts.get(role.id, 0))


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=201,
    **capability(Permission.Role.MANAGE),
)
def create_role(
    body: RoleCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """Create an org-scoped custom role.

    The privilege-escalation guard ensures the new role's permission set is
    ⊆ the actor's own effective permissions and its level is ≤ the actor's.
    """
    from rhesis.backend.ee.rbac.models import Role, RolePermission

    principal = resolve_principal(current_user)
    actor_permissions = _get_actor_permissions(principal, project_id=None, db=db)
    actor_level = _get_actor_level(principal, project_id=None, db=db)

    # Default level for custom roles is just below Member (50) unless a built-in
    # level is specified, which callers cannot set — custom roles are always below
    # Owner/Admin (no free level escalation via create).
    role_level = 50  # custom role default level

    # Validate permission names exist (422) before the escalation guard (403).
    perm_ids = _resolve_permission_ids(body.permission_names, db)
    _check_escalation(body.permission_names, role_level, actor_permissions, actor_level)

    # Friendly conflict (409) instead of a raw IntegrityError from the
    # ix_role_name_org unique index (name, organization_id).
    existing = (
        db.query(Role)
        .filter(
            Role.name == body.name,
            Role.organization_id == current_user.organization_id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A role with this name already exists")

    role = Role(
        name=body.name,
        display_name=body.display_name or body.name,
        description=body.description,
        scope=body.scope,
        level=role_level,
        is_built_in=False,
        organization_id=current_user.organization_id,
    )
    db.add(role)
    db.flush()

    for perm_id in perm_ids:
        db.add(RolePermission(role_id=role.id, permission_id=perm_id))
    db.flush()

    db.refresh(role)
    return _role_to_read(role, db)


@router.put("/roles/{role_id}", response_model=RoleRead, **capability(Permission.Role.MANAGE))
def update_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """Update a custom role's display name and/or permission set.

    Built-in roles are immutable. The privilege-escalation guard applies to
    any new permissions being added.
    """
    from rhesis.backend.ee.rbac.models import RolePermission

    role = _get_role_or_404(role_id, db)
    if role.is_built_in:
        raise HTTPException(status_code=400, detail="Built-in roles are immutable")
    if role.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Role not found")

    principal = resolve_principal(current_user)
    actor_permissions = _get_actor_permissions(principal, project_id=None, db=db)
    actor_level = _get_actor_level(principal, project_id=None, db=db)

    if body.display_name is not None:
        role.display_name = body.display_name

    if body.description is not None:
        role.description = body.description

    if body.permission_names is not None:
        # Validate names exist (422) before escalation guard (403).
        perm_ids = _resolve_permission_ids(body.permission_names, db)
        _check_escalation(body.permission_names, role.level, actor_permissions, actor_level)

        # Bust cache for every holder before rewriting permissions.
        _bust_role_holders(role.id, current_user.organization_id, db)

        # Replace role_permission rows.
        db.query(RolePermission).filter_by(role_id=role.id).delete()
        for perm_id in perm_ids:
            db.add(RolePermission(role_id=role.id, permission_id=perm_id))

    db.flush()
    db.refresh(role)
    counts = _member_counts_for_roles([role.id], current_user.organization_id, db)
    return _role_to_read(role, db, counts.get(role.id, 0))


@router.delete("/roles/{role_id}", status_code=204, **capability(Permission.Role.MANAGE))
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """Soft-delete a custom role and unassign everyone who held it.

    Built-in roles cannot be deleted. The role row is retained (``deleted_at`` is
    stamped) for auditability; the global soft-delete filter then hides it from
    every subsequent query. Rather than blocking the delete when the role is in
    use, holders are actively removed from it:

    - Org-tier members (``organization_member.role_id`` is NOT NULL) are
      reassigned to the built-in **None** role (zero permissions) — access is
      explicitly revoked and must be deliberately re-granted.
    - Project-tier members (``project_membership.role_id`` is nullable) have
      their ``role_id`` cleared, so they fall back to their inherited org role.
    """
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import OrganizationMember, Role

    role = _get_role_or_404(role_id, db)
    if role.is_built_in:
        raise HTTPException(status_code=400, detail="Built-in roles cannot be deleted")
    if role.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Role not found")

    org_id = current_user.organization_id

    # Bust the permission cache for every holder while role_id still points here.
    _bust_role_holders(role.id, org_id, db)

    # Org-tier holders must keep a role (role_id is NOT NULL) — reassign them to
    # the built-in None role. It has organization_id IS NULL, so the lookup must
    # bypass the ambient tenant filter.
    with bypass_tenant_filter():
        none_role = (
            db.query(Role)
            .filter_by(name="None", is_built_in=True, organization_id=None)
            .first()
        )
    if none_role is None:
        # Fail loudly rather than orphan members; None is seeded by migration.
        raise HTTPException(
            status_code=500,
            detail="Built-in None role missing; cannot safely unassign role holders",
        )
    db.query(OrganizationMember).filter_by(role_id=role.id, organization_id=org_id).update(
        {OrganizationMember.role_id: none_role.id}, synchronize_session=False
    )

    # Project-tier holders revert to their inherited org role (role_id nullable).
    db.query(ProjectMembership).filter_by(role_id=role.id, organization_id=org_id).update(
        {ProjectMembership.role_id: None}, synchronize_session=False
    )

    role.soft_delete()
    db.flush()


# ---------------------------------------------------------------------------
# Org-level role assignment
# ---------------------------------------------------------------------------


@router.get(
    "/organization-members",
    response_model=list[OrgMemberRead],
    **capability(Permission.Member.READ),
)
def list_org_members(
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """List all org-level role assignments for the current organization."""
    from rhesis.backend.ee.rbac.models import OrganizationMember

    members = (
        db.query(OrganizationMember).filter_by(organization_id=current_user.organization_id).all()
    )
    return [OrgMemberRead.model_validate(m) for m in members]


@router.put(
    "/organization-members/{user_id}/role",
    response_model=OrgMemberRead,
    **capability(Permission.Member.MANAGE),
)
def assign_org_role(
    user_id: uuid.UUID,
    body: OrgRoleAssign,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """Assign or update the org-level role for a user.

    The privilege-escalation guard ensures you cannot grant a role above your
    own level or whose permissions exceed your own.
    """
    from rhesis.backend.app.models.user import User as UserModel
    from rhesis.backend.ee.rbac.models import SCOPE_ORGANIZATION, OrganizationMember

    principal = resolve_principal(current_user)
    actor_permissions = _get_actor_permissions(principal, project_id=None, db=db)
    actor_level = _get_actor_level(principal, project_id=None, db=db)

    target_role = _get_role_or_404(body.role_id, db)

    # Enforce scope: org-tier assignment requires an org-scoped role.
    if target_role.scope != SCOPE_ORGANIZATION:
        raise HTTPException(
            status_code=422,
            detail="Role is project-scoped and cannot be assigned at the organization tier",
        )

    new_perm_names = _role_permission_names_resolved(target_role, db)
    _check_escalation(new_perm_names, target_role.level, actor_permissions, actor_level)

    # Validate the target user belongs to this org.
    target_user = (
        db.query(UserModel)
        .filter_by(id=user_id, organization_id=current_user.organization_id)
        .first()
    )
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found in this organization")

    # Upsert the organization_member row.
    member = (
        db.query(OrganizationMember)
        .filter_by(
            organization_id=current_user.organization_id,
            user_id=user_id,
        )
        .first()
    )
    if member is not None and member.role_id != body.role_id:
        # Last-owner protection: refuse to demote the sole Owner.
        if _is_last_owner(member, current_user.organization_id, db):
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last Owner of an organization",
            )

    if member is None:
        member = OrganizationMember(
            organization_id=current_user.organization_id,
            user_id=user_id,
            role_id=body.role_id,
        )
        db.add(member)
    else:
        member.role_id = body.role_id
    db.flush()
    db.refresh(member)
    _bust(user_id, current_user.organization_id)
    return OrgMemberRead.model_validate(member)


@router.delete(
    "/organization-members/{user_id}",
    status_code=204,
    **capability(Permission.Member.DELETE),
)
def remove_org_member(
    user_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """Remove the org-level role assignment for a user.

    Refuses if this would leave the org with no Owner (last-owner protection).
    """
    from rhesis.backend.ee.rbac.models import OrganizationMember

    member = (
        db.query(OrganizationMember)
        .filter_by(
            organization_id=current_user.organization_id,
            user_id=user_id,
        )
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Org membership not found")

    if _is_last_owner(member, current_user.organization_id, db):
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the last Owner of an organization",
        )

    _bust(user_id, current_user.organization_id)
    db.delete(member)
    db.flush()


# ---------------------------------------------------------------------------
# Project-level role assignment
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/members",
    response_model=list[ProjectMemberRoleRead],
    **capability(Permission.Member.READ),
)
def list_project_members(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """List all project members with their RBAC role assignments.

    Returns every ``project_membership`` row for *project_id*, including the
    resolved role when ``role_id`` is set.  Members without an explicit
    project-level role have ``role_id`` and ``role`` as ``None``.
    """
    from rhesis.backend.app.models.project_membership import ProjectMembership

    memberships = (
        db.query(ProjectMembership)
        .filter_by(
            project_id=project_id,
            organization_id=current_user.organization_id,
        )
        .all()
    )

    result = []
    for m in memberships:
        role = _load_role(m.role_id, db) if m.role_id is not None else None
        result.append(
            ProjectMemberRoleRead(
                project_id=project_id,
                user_id=m.user_id,
                role_id=m.role_id,
                role=_role_to_read(role, db) if role is not None else None,
            )
        )
    return result


@router.put(
    "/projects/{project_id}/members/{user_id}/role",
    response_model=ProjectMemberRoleRead,
    status_code=200,
    **capability(Permission.Member.MANAGE),
)
def assign_project_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ProjectMemberRoleAssign,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
    _org=_RBAC_DEP,
):
    """Assign or update the project-level role for a user.

    The user must already be a project member (added via the community
    membership endpoint). The privilege-escalation guard applies.
    """
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.ee.rbac.schemas import ProjectMemberRoleRead

    target_role = check_project_role_assignment(db, current_user, body.role_id, project_id)

    membership = (
        db.query(ProjectMembership)
        .filter_by(
            project_id=project_id,
            user_id=user_id,
            organization_id=current_user.organization_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Project membership not found")

    membership.role_id = body.role_id
    db.flush()
    _bust(user_id, current_user.organization_id)
    return ProjectMemberRoleRead(
        project_id=project_id,
        user_id=user_id,
        role_id=body.role_id,
        role=_role_to_read(target_role, db),
    )


__all__ = ["router"]
