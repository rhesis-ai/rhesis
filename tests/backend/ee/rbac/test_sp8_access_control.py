"""SP8 comprehensive access-control tests.

Exercises the full RBAC stack end-to-end against a real database:

1. Permission matrix for every built-in role (Owner / Admin / Member / Viewer / None).
2. Project role overrides org role (not a union).
3. Custom role create → assign → verify → update → delete lifecycle.
4. Multi-user scenarios: escalation guard, ownership transfer, mixed tiers.
5. Org-member API: assign, demote-last-owner, remove, foreign-user guard.
6. Project-member API: assign, scope enforcement.
7. Role catalog API: create, update, delete-in-use guard.
8. FK integrity: project_membership.role_id → role.id ON DELETE SET NULL.

All tests use a real DB (``test_db`` fixture) and call router functions or the
provider directly — no HTTP layer needed because the logic under test lives in
the service/provider tier.

EE modules are imported at module load (mirroring ``test_sp8_provider.py``):
this suite only runs where the EE package is installed, so there is no
Community-only collection path to guard against.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_sp8_access_control.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.ee.rbac.models import (
    SCOPE_ORGANIZATION,
    SCOPE_PROJECT,
    OrganizationMember,
    Permission,
    Role,
    RolePermission,
)
from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider
from rhesis.backend.ee.rbac.router import (
    assign_org_role,
    assign_project_role,
    create_role,
    delete_role,
    list_org_members,
    list_roles,
    remove_org_member,
    update_role,
)
from rhesis.backend.ee.rbac.schemas import (
    OrgRoleAssign,
    ProjectMemberRoleAssign,
    RoleCreate,
    RoleUpdate,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
#
# The permission catalog and the five built-in roles are seeded once by the
# Alembic migrations the ``test_db`` fixture runs, so no per-test catalog sync
# is needed.  Built-in role permissions are computed from code by the provider
# (``permissions_for_built_in_role``); custom roles use ``role_permission``.


@contextmanager
def _rbac_enabled():
    """Force the EE provider to treat RBAC as licensed for the duration.

    Patches at the *class* level so it covers both the ``self.provider``
    instances used by the direct-authorization tests and the fresh providers
    the router constructs internally (e.g. ``resolve_effective_role``).
    """
    with patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True):
        yield


def _builtin_role(db: Session, name: str) -> Role:
    with bypass_tenant_filter():
        role = db.query(Role).filter_by(name=name, is_built_in=True).first()
    assert role is not None, f"Built-in role '{name}' not seeded by migrations"
    return role


def _create_org(db: Session) -> uuid.UUID:
    org_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO organization (id, name, is_active) VALUES (:id, :name, true)"),
        {"id": str(org_id), "name": f"TestOrg-{org_id.hex[:8]}"},
    )
    db.flush()
    return org_id


def _create_user(db: Session, org_id: uuid.UUID) -> uuid.UUID:
    user_id = uuid.uuid4()
    db.execute(
        text(
            'INSERT INTO "user" (id, email, organization_id, is_active) '
            "VALUES (:id, :email, :oid, true)"
        ),
        {"id": str(user_id), "email": f"u-{user_id.hex[:8]}@test.example", "oid": str(org_id)},
    )
    db.flush()
    return user_id


def _create_project(db: Session, org_id: uuid.UUID) -> uuid.UUID:
    pid = uuid.uuid4()
    db.execute(
        text("INSERT INTO project (id, name, organization_id) VALUES (:id, :name, :oid)"),
        {"id": str(pid), "name": f"Proj-{pid.hex[:8]}", "oid": str(org_id)},
    )
    db.flush()
    return pid


def _custom_role(db: Session, org_id: uuid.UUID, *, name: str, scope: str, level: int = 50) -> Role:
    """Create an org-owned custom role row directly (bypassing the escalation guard)."""
    role = Role(
        name=name,
        display_name=name,
        scope=scope,
        level=level,
        is_built_in=False,
        organization_id=org_id,
    )
    db.add(role)
    db.flush()
    return role


def _grant_permission(db: Session, role_id: uuid.UUID, permission_name: str) -> None:
    perm = db.query(Permission).filter_by(name=permission_name).first()
    assert perm is not None, f"Permission '{permission_name}' not in catalog"
    db.add(RolePermission(role_id=role_id, permission_id=perm.id))
    db.flush()


def _assign_org_role(db: Session, org_id: uuid.UUID, user_id: uuid.UUID, role_name: str) -> None:
    role = _builtin_role(db, role_name)
    existing = (
        db.query(OrganizationMember).filter_by(organization_id=org_id, user_id=user_id).first()
    )
    if existing:
        existing.role_id = role.id
    else:
        db.add(OrganizationMember(organization_id=org_id, user_id=user_id, role_id=role.id))
    db.flush()


def _add_project_member(
    db: Session,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID | None = None,
) -> None:
    existing = db.query(ProjectMembership).filter_by(project_id=project_id, user_id=user_id).first()
    if existing:
        existing.role_id = role_id
    else:
        db.add(
            ProjectMembership(
                project_id=project_id,
                user_id=user_id,
                organization_id=org_id,
                role_id=role_id,
            )
        )
    db.flush()


def _assign_project_role(
    db: Session,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role_name: str,
) -> None:
    _add_project_member(db, org_id, project_id, user_id, _builtin_role(db, role_name).id)


def _principal(user_id: uuid.UUID, org_id: uuid.UUID) -> Principal:
    return Principal(user_id=user_id, organization_id=org_id, kind="session")


def _user(user_id: uuid.UUID, org_id: uuid.UUID) -> MagicMock:
    """Lightweight ``current_user`` stand-in for router calls."""
    u = MagicMock()
    u.id = user_id
    u.organization_id = org_id
    return u


def _authorized(
    db: Session,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    permission: str,
    project_id: uuid.UUID | None = None,
) -> bool:
    """Resolve an authorization decision for *user_id* with RBAC forced on."""
    with _rbac_enabled():
        return PermissionAuthorizationProvider().is_authorized(
            _principal(user_id, org_id), permission, project_id=project_id, db=db
        )


# ---------------------------------------------------------------------------
# 1. Permission matrix — every built-in role
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestAccessMatrix:
    """Each built-in role should allow/deny the expected capability set."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)

    def _check(self, role_name: str, permission: str) -> bool:
        user_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, user_id, role_name)
        return _authorized(self.db, user_id, self.org_id, permission)

    # Owner
    def test_owner_can_read_test_set(self):
        assert self._check("Owner", "test_set:read")

    def test_owner_can_manage_roles(self):
        assert self._check("Owner", "role:manage")

    def test_owner_can_manage_sso(self):
        assert self._check("Owner", "sso:manage")

    def test_owner_can_manage_members(self):
        assert self._check("Owner", "member:manage")

    # Admin
    def test_admin_can_read_test_set(self):
        assert self._check("Admin", "test_set:read")

    def test_admin_can_create_test_set(self):
        assert self._check("Admin", "test_set:create")

    def test_admin_can_manage_members(self):
        assert self._check("Admin", "member:manage")

    def test_admin_cannot_manage_roles(self):
        assert not self._check("Admin", "role:manage")

    def test_admin_cannot_manage_sso(self):
        assert not self._check("Admin", "sso:manage")

    def test_admin_cannot_read_roles(self):
        assert not self._check("Admin", "role:read")

    # Member
    def test_member_can_read_test_set(self):
        assert self._check("Member", "test_set:read")

    def test_member_can_create_test_set(self):
        assert self._check("Member", "test_set:create")

    def test_member_can_read_org_context(self):
        # Member ⊇ Viewer, which holds org-context reads (organization:read).
        assert self._check("Member", "organization:read")

    def test_member_cannot_read_roles(self):
        # role:read / token:read are sensitive org-admin reads, withheld below Owner.
        assert not self._check("Member", "role:read")

    def test_member_cannot_manage_members(self):
        assert not self._check("Member", "member:manage")

    def test_member_cannot_manage_roles(self):
        assert not self._check("Member", "role:manage")

    # Viewer
    def test_viewer_can_read_test_set(self):
        assert self._check("Viewer", "test_set:read")

    def test_viewer_can_read_test(self):
        assert self._check("Viewer", "test:read")

    def test_viewer_cannot_create_test_set(self):
        assert not self._check("Viewer", "test_set:create")

    def test_viewer_cannot_update_test_set(self):
        assert not self._check("Viewer", "test_set:update")

    def test_viewer_cannot_manage_members(self):
        assert not self._check("Viewer", "member:manage")

    def test_viewer_can_read_org_context(self):
        assert self._check("Viewer", "organization:read")
        assert self._check("Viewer", "member:read")

    def test_viewer_cannot_read_sensitive_org_admin(self):
        assert not self._check("Viewer", "role:read")
        assert not self._check("Viewer", "token:read")

    # None role — every permission denied
    def test_none_role_denies_read(self):
        assert not self._check("None", "test_set:read")

    def test_none_role_denies_create(self):
        assert not self._check("None", "test_set:create")

    def test_none_role_denies_org_read(self):
        assert not self._check("None", "organization:read")

    # No membership at all — denied
    def test_no_membership_denies_all(self):
        user_id = _create_user(self.db, self.org_id)
        assert not _authorized(self.db, user_id, self.org_id, "test_set:read")


# ---------------------------------------------------------------------------
# 2. Project role overrides org role
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestProjectRoleOverride:
    """Project role beats org role (override, not a union)."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)
        self.user_id = _create_user(test_db, self.org_id)

    def _can_project(self, perm: str) -> bool:
        return _authorized(self.db, self.user_id, self.org_id, perm, project_id=self.project_id)

    def test_viewer_project_role_overrides_admin_org_role_create(self):
        """Admin org → can create; but Viewer project role → cannot create."""
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        _assign_project_role(self.db, self.org_id, self.project_id, self.user_id, "Viewer")
        assert not self._can_project("test_set:create")

    def test_viewer_project_role_still_allows_read(self):
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        _assign_project_role(self.db, self.org_id, self.project_id, self.user_id, "Viewer")
        assert self._can_project("test_set:read")

    def test_none_project_role_blocks_admin_org_permissions(self):
        """Even Admin org role is blocked when project role is None."""
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        _assign_project_role(self.db, self.org_id, self.project_id, self.user_id, "None")
        assert not self._can_project("test_set:read")

    def test_org_role_applies_when_no_project_role_set(self):
        """Without a project-level row the org role governs."""
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        assert self._can_project("test_set:create")

    def test_different_users_have_independent_project_roles(self):
        """Two users, different project roles, independent decisions."""
        viewer_id = _create_user(self.db, self.org_id)
        member_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, viewer_id, "Admin")
        _assign_org_role(self.db, self.org_id, member_id, "Admin")
        _assign_project_role(self.db, self.org_id, self.project_id, viewer_id, "Viewer")
        _assign_project_role(self.db, self.org_id, self.project_id, member_id, "Member")

        assert not _authorized(
            self.db, viewer_id, self.org_id, "test_set:create", project_id=self.project_id
        )
        assert _authorized(
            self.db, member_id, self.org_id, "test_set:create", project_id=self.project_id
        )


# ---------------------------------------------------------------------------
# 3. Custom role lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestCustomRoleLifecycle:
    """Create a custom role, assign it, verify access, update, delete."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.actor_id = _create_user(test_db, self.org_id)
        # Actor is an Owner (all permissions → can create any role below them).
        _assign_org_role(test_db, self.org_id, self.actor_id, "Owner")
        self.actor = _user(self.actor_id, self.org_id)

    def _create(self, body: RoleCreate):
        with _rbac_enabled():
            return create_role(body=body, db=self.db, current_user=self.actor, _org=None)

    def _can(self, user_id: uuid.UUID, perm: str) -> bool:
        return _authorized(self.db, user_id, self.org_id, perm)

    def _assign_member(self, role_id: uuid.UUID) -> uuid.UUID:
        target_id = _create_user(self.db, self.org_id)
        self.db.add(
            OrganizationMember(organization_id=self.org_id, user_id=target_id, role_id=role_id)
        )
        self.db.flush()
        return target_id

    def test_create_custom_org_role(self):
        result = self._create(
            RoleCreate(
                name="TestReader",
                display_name="Test Reader",
                scope="organization",
                permission_names=["test_set:read", "test:read"],
            )
        )
        assert result.name == "TestReader"
        assert result.is_built_in is False
        assert result.organization_id == self.org_id
        assert {p.name for p in result.permissions} == {"test_set:read", "test:read"}

    def test_assign_custom_role_and_check_access(self):
        role_data = self._create(
            RoleCreate(name="DataReader", scope="organization", permission_names=["test_set:read"])
        )
        target_id = self._assign_member(role_data.id)
        assert self._can(target_id, "test_set:read") is True
        assert self._can(target_id, "test_set:create") is False

    def test_update_custom_role_changes_permissions(self):
        role_data = self._create(
            RoleCreate(name="MutableRole", scope="organization", permission_names=["test:read"])
        )
        target_id = self._assign_member(role_data.id)
        assert self._can(target_id, "test:read") is True
        assert self._can(target_id, "test_set:read") is False

        # Add test_set:read to the role.
        with _rbac_enabled():
            update_role(
                role_id=role_data.id,
                body=RoleUpdate(permission_names=["test:read", "test_set:read"]),
                db=self.db,
                current_user=self.actor,
                _org=None,
            )
        assert self._can(target_id, "test_set:read") is True

    def test_delete_custom_role_in_use_raises_409(self):
        role_data = self._create(
            RoleCreate(name="InUseRole", scope="organization", permission_names=[])
        )
        self._assign_member(role_data.id)
        with pytest.raises(HTTPException) as exc:
            delete_role(role_id=role_data.id, db=self.db, current_user=self.actor, _org=None)
        assert exc.value.status_code == 409

    def test_delete_custom_role_succeeds_when_unassigned(self):
        role_data = self._create(
            RoleCreate(name="UnusedRole", scope="organization", permission_names=[])
        )
        # Should not raise.
        delete_role(role_id=role_data.id, db=self.db, current_user=self.actor, _org=None)

    def test_cannot_delete_builtin_role(self):
        viewer = _builtin_role(self.db, "Viewer")
        with pytest.raises(HTTPException) as exc:
            delete_role(role_id=viewer.id, db=self.db, current_user=self.actor, _org=None)
        assert exc.value.status_code == 400

    def test_create_role_with_unknown_permission_raises_422(self):
        with pytest.raises(HTTPException) as exc:
            self._create(
                RoleCreate(
                    name="BadRole",
                    scope="organization",
                    permission_names=["nonexistent:permission"],
                )
            )
        assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# 4. Multi-user scenarios
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestMultiUserScenarios:
    """Multiple users interacting with the RBAC system."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)

    def _assign(self, actor_id: uuid.UUID, target_id: uuid.UUID, role: Role):
        with _rbac_enabled():
            return assign_org_role(
                user_id=target_id,
                body=OrgRoleAssign(role_id=role.id),
                db=self.db,
                current_user=_user(actor_id, self.org_id),
                _org=None,
            )

    def test_owner_can_assign_admin_to_new_user(self):
        owner_id = _create_user(self.db, self.org_id)
        target_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        result = self._assign(owner_id, target_id, _builtin_role(self.db, "Admin"))
        assert result.role_id == _builtin_role(self.db, "Admin").id
        assert result.user_id == target_id

    def test_admin_cannot_grant_owner_role(self):
        """Privilege-escalation guard: Admin (level 80) cannot grant Owner (level 100)."""
        admin_id = _create_user(self.db, self.org_id)
        target_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")
        _assign_org_role(self.db, self.org_id, target_id, "Member")

        with pytest.raises(HTTPException) as exc:
            self._assign(admin_id, target_id, _builtin_role(self.db, "Owner"))
        assert exc.value.status_code == 403

    def test_owner_can_demote_when_second_owner_exists(self):
        """Two Owners present — demotion of one is allowed."""
        owner1_id = _create_user(self.db, self.org_id)
        owner2_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner1_id, "Owner")
        _assign_org_role(self.db, self.org_id, owner2_id, "Owner")

        result = self._assign(owner1_id, owner2_id, _builtin_role(self.db, "Admin"))
        assert result.role_id == _builtin_role(self.db, "Admin").id

    def test_sole_owner_cannot_be_demoted(self):
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        with pytest.raises(HTTPException) as exc:
            self._assign(owner_id, owner_id, _builtin_role(self.db, "Admin"))
        assert exc.value.status_code == 400
        assert "last Owner" in exc.value.detail

    def test_sole_owner_cannot_be_removed(self):
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        with pytest.raises(HTTPException) as exc, _rbac_enabled():
            remove_org_member(
                user_id=owner_id,
                db=self.db,
                current_user=_user(owner_id, self.org_id),
                _org=None,
            )
        assert exc.value.status_code == 400

    def test_assign_rejects_foreign_user(self):
        """User from a different org → 404."""
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        other_org = _create_org(self.db)
        foreign_user_id = _create_user(self.db, other_org)

        with pytest.raises(HTTPException) as exc:
            self._assign(owner_id, foreign_user_id, _builtin_role(self.db, "Viewer"))
        assert exc.value.status_code == 404
        assert "organization" in exc.value.detail.lower()

    def test_multiple_users_multiple_roles_permission_matrix(self):
        """Spot-check a 4-user x mixed-permission matrix in one test."""
        users = {}
        for r in ("Owner", "Admin", "Member", "Viewer"):
            uid = _create_user(self.db, self.org_id)
            _assign_org_role(self.db, self.org_id, uid, r)
            users[r] = uid

        expected = {
            ("Owner", "test_set:read"): True,
            ("Owner", "role:manage"): True,
            ("Admin", "test_set:create"): True,
            ("Admin", "role:manage"): False,
            ("Member", "test_set:create"): True,
            ("Member", "member:manage"): False,
            ("Viewer", "test_set:read"): True,
            ("Viewer", "test_set:create"): False,
        }
        for (role, perm), want in expected.items():
            got = _authorized(self.db, users[role], self.org_id, perm)
            assert got == want, f"role={role} perm={perm}: expected {want}, got {got}"


# ---------------------------------------------------------------------------
# 5. Project-level assignment API
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestProjectMemberAPI:
    """assign_project_role endpoint — scope guard, membership-required."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)
        self.owner_id = _create_user(test_db, self.org_id)
        _assign_org_role(test_db, self.org_id, self.owner_id, "Owner")
        self.actor = _user(self.owner_id, self.org_id)

    def _assign(self, project_id: uuid.UUID, user_id: uuid.UUID, role: Role):
        with _rbac_enabled():
            return assign_project_role(
                project_id=project_id,
                user_id=user_id,
                body=ProjectMemberRoleAssign(role_id=role.id),
                db=self.db,
                current_user=self.actor,
                _org=None,
            )

    def test_assign_project_scoped_role_succeeds(self):
        role = _custom_role(self.db, self.org_id, name="ProjReader", scope=SCOPE_PROJECT)
        _grant_permission(self.db, role.id, "test_set:read")

        target_id = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, target_id)

        result = self._assign(self.project_id, target_id, role)
        assert result.role_id == role.id
        assert result.project_id == self.project_id

    def test_assign_builtin_org_scoped_role_to_project_succeeds(self):
        """Built-in Admin (scope='organization') now binds down to the project tier.

        Under the one-directional gate model (K8s ClusterRole semantics), org/built-in
        roles bind down to projects.  Only Owner (level 100) and None (level 0) are
        rejected at the project tier.
        """
        target_id = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, target_id)

        admin_role = _builtin_role(self.db, "Admin")
        result = self._assign(self.project_id, target_id, admin_role)
        assert result.role_id == admin_role.id
        assert result.project_id == self.project_id

    def test_assign_owner_to_project_raises_422(self):
        """Owner (level 100) cannot be assigned at the project tier."""
        target_id = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, target_id)

        with pytest.raises(HTTPException) as exc:
            self._assign(self.project_id, target_id, _builtin_role(self.db, "Owner"))
        assert exc.value.status_code == 422

    def test_assign_none_to_project_raises_422(self):
        """None (level 0) cannot be assigned at the project tier."""
        target_id = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, target_id)

        with pytest.raises(HTTPException) as exc:
            self._assign(self.project_id, target_id, _builtin_role(self.db, "None"))
        assert exc.value.status_code == 422

    def test_assign_role_to_non_member_raises_404(self):
        role = _custom_role(self.db, self.org_id, name="ProjRole2", scope=SCOPE_PROJECT)
        non_member_id = _create_user(self.db, self.org_id)

        with pytest.raises(HTTPException) as exc:
            self._assign(self.project_id, non_member_id, role)
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 6. Org-member listing
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestOrgMemberListing:
    """list_org_members returns only the current org's assignments."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)

    def test_list_members_returns_assigned_users(self):
        u1 = _create_user(self.db, self.org_id)
        u2 = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, u1, "Admin")
        _assign_org_role(self.db, self.org_id, u2, "Viewer")

        results = list_org_members(db=self.db, current_user=_user(u1, self.org_id), _org=None)
        user_ids = {r.user_id for r in results}
        assert {u1, u2} <= user_ids

    def test_list_members_excludes_other_org_users(self):
        other_org = _create_org(self.db)
        u_mine = _create_user(self.db, self.org_id)
        u_other = _create_user(self.db, other_org)
        _assign_org_role(self.db, self.org_id, u_mine, "Admin")
        _assign_org_role(self.db, other_org, u_other, "Admin")

        results = list_org_members(db=self.db, current_user=_user(u_mine, self.org_id), _org=None)
        assert u_other not in {r.user_id for r in results}


# ---------------------------------------------------------------------------
# 7. Role catalog listing
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestRoleCatalogListing:
    """list_roles returns built-ins + org-owned custom roles, not other orgs'."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.user_id = _create_user(test_db, self.org_id)
        _assign_org_role(test_db, self.org_id, self.user_id, "Owner")
        self.actor = _user(self.user_id, self.org_id)

    def _list_names(self) -> set[str]:
        return {r.name for r in list_roles(db=self.db, current_user=self.actor, _org=None)}

    def test_list_roles_includes_builtin_roles(self):
        assert {"Owner", "Admin", "Member", "Viewer", "None"} <= self._list_names()

    def test_list_roles_includes_own_custom_role(self):
        _custom_role(self.db, self.org_id, name="OrgCustom", scope=SCOPE_ORGANIZATION)
        assert "OrgCustom" in self._list_names()

    def test_list_roles_excludes_other_org_custom_roles(self):
        other_org = _create_org(self.db)
        _custom_role(self.db, other_org, name="ForeignRole", scope=SCOPE_ORGANIZATION)
        assert "ForeignRole" not in self._list_names()


# ---------------------------------------------------------------------------
# 8. FK integrity: project_membership.role_id ON DELETE SET NULL
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestProjectMembershipRoleFK:
    """The FK clears role_id when the referenced role is deleted, and rejects bad refs."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)

    def test_delete_role_nulls_project_membership_role_id(self):
        role = _custom_role(self.db, self.org_id, name="TmpProjRole", scope=SCOPE_PROJECT)
        user_id = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, user_id, role.id)

        # Delete the role via raw SQL (no org member uses it; the role-table
        # RESTRICT FK is unrelated to project_membership).
        self.db.execute(text("DELETE FROM role WHERE id = :rid"), {"rid": str(role.id)})
        self.db.flush()
        self.db.expire_all()

        refreshed = (
            self.db.query(ProjectMembership)
            .filter_by(project_id=self.project_id, user_id=user_id)
            .first()
        )
        assert refreshed is not None
        assert refreshed.role_id is None, (
            "FK ON DELETE SET NULL must clear role_id when the referenced role is deleted"
        )

    def test_invalid_role_id_raises_fk_violation(self):
        """Inserting a non-existent role_id raises an IntegrityError."""
        user_id = _create_user(self.db, self.org_id)

        with pytest.raises(IntegrityError):
            self.db.execute(
                text(
                    "INSERT INTO project_membership "
                    "(project_id, user_id, organization_id, role_id) "
                    "VALUES (:pid, :uid, :oid, :rid)"
                ),
                {
                    "pid": str(self.project_id),
                    "uid": str(user_id),
                    "oid": str(self.org_id),
                    "rid": str(uuid.uuid4()),
                },
            )
            self.db.flush()
