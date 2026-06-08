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

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_sp8_access_control.py -v
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _do_sync(db: Session, capabilities: list[str] | None = None) -> None:
    from rhesis.backend.ee.rbac.sync import sync_rbac_catalog

    if capabilities is None:
        sync_rbac_catalog(db)
        return

    with patch(
        "rhesis.backend.app.auth.capabilities.get_all_capabilities",
        return_value=capabilities,
    ):
        sync_rbac_catalog(db)


def _get_builtin_role(db: Session, name: str):
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import Role

    with bypass_tenant_filter():
        return db.query(Role).filter_by(name=name, is_built_in=True).first()


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


def _assign_org_role(db: Session, org_id: uuid.UUID, user_id: uuid.UUID, role_name: str) -> None:
    from rhesis.backend.ee.rbac.models import OrganizationMember

    role = _get_builtin_role(db, role_name)
    assert role is not None, f"Built-in role '{role_name}' not seeded"
    existing = (
        db.query(OrganizationMember).filter_by(organization_id=org_id, user_id=user_id).first()
    )
    if existing:
        existing.role_id = role.id
    else:
        db.add(OrganizationMember(organization_id=org_id, user_id=user_id, role_id=role.id))
    db.flush()


def _assign_project_role(
    db: Session,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role_name: str,
) -> None:
    from rhesis.backend.app.models.project_membership import ProjectMembership

    role = _get_builtin_role(db, role_name)
    assert role is not None
    existing = db.query(ProjectMembership).filter_by(project_id=project_id, user_id=user_id).first()
    if existing:
        existing.role_id = role.id
    else:
        db.add(
            ProjectMembership(
                project_id=project_id,
                user_id=user_id,
                organization_id=org_id,
                role_id=role.id,
            )
        )
    db.flush()


def _make_principal(user_id: uuid.UUID, org_id: uuid.UUID):
    from rhesis.backend.app.auth.principal import Principal

    return Principal(user_id=user_id, organization_id=org_id, kind="session")


def _mock_current_user(user_id: uuid.UUID, org_id: uuid.UUID) -> Any:
    """Construct a lightweight User-like mock for router calls."""
    user = MagicMock()
    user.id = user_id
    user.organization_id = org_id
    return user


def _can(provider, principal, permission: str, db: Session, project_id=None) -> bool:
    return provider.is_authorized(principal, permission, project_id=project_id, db=db)


# ---------------------------------------------------------------------------
# 1. Permission matrix — every built-in role
# ---------------------------------------------------------------------------


CAPS = [
    "test_set:read",
    "test_set:create",
    "test_set:update",
    "test_set:delete",
    "test:read",
    "test:create",
    "organization:read",
    "organization:update",
    "member:read",
    "member:manage",
    "role:read",
    "role:manage",
    "sso:manage",
]


@pytest.mark.ee
@pytest.mark.integration
class TestAccessMatrix:
    """Each built-in role should allow/deny the expected capability set."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        _do_sync(test_db, CAPS)
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        self.provider = PermissionAuthorizationProvider()

    def _check(self, role_name: str, permission: str, project_id=None) -> bool:
        user_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, user_id, role_name)
        principal = _make_principal(user_id, self.org_id)
        with patch.object(self.provider, "_rbac_available", return_value=True):
            return _can(self.provider, principal, permission, self.db, project_id)

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

    def test_member_cannot_read_org(self):
        assert not self._check("Member", "organization:read")

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
        principal = _make_principal(user_id, self.org_id)
        with patch.object(self.provider, "_rbac_available", return_value=True):
            assert not _can(self.provider, principal, "test_set:read", self.db)


# ---------------------------------------------------------------------------
# 2. Project role overrides org role
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestProjectRoleOverride:
    """Project role beats org role (not a union).

    Scenario A — Viewer project role silences Admin org permissions.
    Scenario B — A project-scoped custom role gives access the org role lacks.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        _do_sync(
            test_db,
            ["test_set:read", "test_set:create", "test_set:update", "organization:update"],
        )
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)
        self.user_id = _create_user(test_db, self.org_id)

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        self.provider = PermissionAuthorizationProvider()

    def _can_project(self, perm: str) -> bool:
        principal = _make_principal(self.user_id, self.org_id)
        with patch.object(self.provider, "_rbac_available", return_value=True):
            return _can(self.provider, principal, perm, self.db, self.project_id)

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

        p_viewer = _make_principal(viewer_id, self.org_id)
        p_member = _make_principal(member_id, self.org_id)
        with patch.object(self.provider, "_rbac_available", return_value=True):
            viewer_can_create = _can(
                self.provider, p_viewer, "test_set:create", self.db, self.project_id
            )
            member_can_create = _can(
                self.provider, p_member, "test_set:create", self.db, self.project_id
            )
        assert not viewer_can_create
        assert member_can_create


# ---------------------------------------------------------------------------
# 3. Custom role lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestCustomRoleLifecycle:
    """Create a custom role, assign it, verify access, update, delete."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        _do_sync(test_db, ["test_set:read", "test_set:create", "test:read"])
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)
        self.actor_id = _create_user(test_db, self.org_id)
        # Actor is an Owner (all permissions → can create any role below them).
        _assign_org_role(test_db, self.org_id, self.actor_id, "Owner")
        self.actor = _mock_current_user(self.actor_id, self.org_id)

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        self.provider = PermissionAuthorizationProvider()

    def _is_authorized(self, user_id: uuid.UUID, perm: str) -> bool:
        p = _make_principal(user_id, self.org_id)
        with patch.object(self.provider, "_rbac_available", return_value=True):
            return _can(self.provider, p, perm, self.db)

    def test_create_custom_org_role(self):
        from rhesis.backend.ee.rbac.router import create_role
        from rhesis.backend.ee.rbac.schemas import RoleCreate

        body = RoleCreate(
            name="TestReader",
            display_name="Test Reader",
            scope="organization",
            permission_names=["test_set:read", "test:read"],
        )
        with patch.object(self.provider, "_rbac_available", return_value=True):
            result = create_role(body=body, db=self.db, current_user=self.actor, _org=None)

        assert result.name == "TestReader"
        assert result.is_built_in is False
        assert result.organization_id == self.org_id
        assert {p.name for p in result.permissions} == {"test_set:read", "test:read"}

    def test_assign_custom_role_and_check_access(self):
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role
        from rhesis.backend.ee.rbac.router import create_role
        from rhesis.backend.ee.rbac.schemas import RoleCreate

        body = RoleCreate(
            name="DataReader",
            scope="organization",
            permission_names=["test_set:read"],
        )
        with patch.object(self.provider, "_rbac_available", return_value=True):
            role_data = create_role(body=body, db=self.db, current_user=self.actor, _org=None)

        target_id = _create_user(self.db, self.org_id)
        from rhesis.backend.app.scope import bypass_tenant_filter

        with bypass_tenant_filter():
            role = self.db.query(Role).filter_by(id=role_data.id).first()
        self.db.add(
            OrganizationMember(organization_id=self.org_id, user_id=target_id, role_id=role.id)
        )
        self.db.flush()

        assert self._is_authorized(target_id, "test_set:read") is True
        assert self._is_authorized(target_id, "test_set:create") is False

    def test_update_custom_role_changes_permissions(self):
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role
        from rhesis.backend.ee.rbac.router import create_role, update_role
        from rhesis.backend.ee.rbac.schemas import RoleCreate, RoleUpdate

        body = RoleCreate(name="MutableRole", scope="organization", permission_names=["test:read"])
        with patch.object(self.provider, "_rbac_available", return_value=True):
            role_data = create_role(body=body, db=self.db, current_user=self.actor, _org=None)

        target_id = _create_user(self.db, self.org_id)
        with bypass_tenant_filter():
            role = self.db.query(Role).filter_by(id=role_data.id).first()
        self.db.add(
            OrganizationMember(organization_id=self.org_id, user_id=target_id, role_id=role.id)
        )
        self.db.flush()

        assert self._is_authorized(target_id, "test:read") is True
        assert self._is_authorized(target_id, "test_set:read") is False

        # Add test_set:read to the role.
        update_body = RoleUpdate(permission_names=["test:read", "test_set:read"])
        with patch.object(self.provider, "_rbac_available", return_value=True):
            update_role(
                role_id=role_data.id,
                body=update_body,
                db=self.db,
                current_user=self.actor,
                _org=None,
            )

        assert self._is_authorized(target_id, "test_set:read") is True

    def test_delete_custom_role_in_use_raises_409(self):
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role
        from rhesis.backend.ee.rbac.router import create_role, delete_role
        from rhesis.backend.ee.rbac.schemas import RoleCreate

        body = RoleCreate(name="InUseRole", scope="organization", permission_names=[])
        with patch.object(self.provider, "_rbac_available", return_value=True):
            role_data = create_role(body=body, db=self.db, current_user=self.actor, _org=None)

        target_id = _create_user(self.db, self.org_id)
        with bypass_tenant_filter():
            role = self.db.query(Role).filter_by(id=role_data.id).first()
        self.db.add(
            OrganizationMember(organization_id=self.org_id, user_id=target_id, role_id=role.id)
        )
        self.db.flush()

        with pytest.raises(HTTPException) as exc:
            delete_role(
                role_id=role_data.id,
                db=self.db,
                current_user=self.actor,
                _org=None,
            )
        assert exc.value.status_code == 409

    def test_delete_custom_role_succeeds_when_unassigned(self):
        from rhesis.backend.ee.rbac.router import create_role, delete_role
        from rhesis.backend.ee.rbac.schemas import RoleCreate

        body = RoleCreate(name="UnusedRole", scope="organization", permission_names=[])
        with patch.object(self.provider, "_rbac_available", return_value=True):
            role_data = create_role(body=body, db=self.db, current_user=self.actor, _org=None)
        # Should not raise.
        delete_role(role_id=role_data.id, db=self.db, current_user=self.actor, _org=None)

    def test_cannot_delete_builtin_role(self):
        from rhesis.backend.ee.rbac.router import delete_role

        viewer = _get_builtin_role(self.db, "Viewer")
        with pytest.raises(HTTPException) as exc:
            delete_role(role_id=viewer.id, db=self.db, current_user=self.actor, _org=None)
        assert exc.value.status_code == 400

    def test_create_role_with_unknown_permission_raises_422(self):
        from rhesis.backend.ee.rbac.router import create_role
        from rhesis.backend.ee.rbac.schemas import RoleCreate

        body = RoleCreate(
            name="BadRole",
            scope="organization",
            permission_names=["nonexistent:permission"],
        )
        with pytest.raises(HTTPException) as exc:
            create_role(body=body, db=self.db, current_user=self.actor, _org=None)
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
        _do_sync(test_db, ["test_set:read", "test_set:create", "member:manage", "role:manage"])
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)

    def test_owner_can_assign_admin_to_new_user(self):
        from rhesis.backend.ee.rbac.router import assign_org_role
        from rhesis.backend.ee.rbac.schemas import OrgRoleAssign

        owner_id = _create_user(self.db, self.org_id)
        target_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        owner_user = _mock_current_user(owner_id, self.org_id)
        admin_role = _get_builtin_role(self.db, "Admin")

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True):
            result = assign_org_role(
                user_id=target_id,
                body=OrgRoleAssign(role_id=admin_role.id),
                db=self.db,
                current_user=owner_user,
                _org=None,
            )
        assert result.role_id == admin_role.id
        assert result.user_id == target_id

    def test_admin_cannot_grant_owner_role(self):
        """Privilege-escalation guard: Admin (level 80) cannot grant Owner (level 100)."""
        from rhesis.backend.ee.rbac.router import assign_org_role
        from rhesis.backend.ee.rbac.schemas import OrgRoleAssign

        admin_id = _create_user(self.db, self.org_id)
        target_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")
        _assign_org_role(self.db, self.org_id, target_id, "Member")

        admin_user = _mock_current_user(admin_id, self.org_id)
        owner_role = _get_builtin_role(self.db, "Owner")

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with (
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            assign_org_role(
                user_id=target_id,
                body=OrgRoleAssign(role_id=owner_role.id),
                db=self.db,
                current_user=admin_user,
                _org=None,
            )
        assert exc.value.status_code == 403

    def test_owner_can_demote_when_second_owner_exists(self):
        """Two Owners present — demotion of one is allowed."""
        from rhesis.backend.ee.rbac.router import assign_org_role
        from rhesis.backend.ee.rbac.schemas import OrgRoleAssign

        owner1_id = _create_user(self.db, self.org_id)
        owner2_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner1_id, "Owner")
        _assign_org_role(self.db, self.org_id, owner2_id, "Owner")

        actor = _mock_current_user(owner1_id, self.org_id)
        admin_role = _get_builtin_role(self.db, "Admin")

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True):
            result = assign_org_role(
                user_id=owner2_id,
                body=OrgRoleAssign(role_id=admin_role.id),
                db=self.db,
                current_user=actor,
                _org=None,
            )
        assert result.role_id == admin_role.id

    def test_sole_owner_cannot_be_demoted(self):
        from rhesis.backend.ee.rbac.router import assign_org_role
        from rhesis.backend.ee.rbac.schemas import OrgRoleAssign

        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        actor = _mock_current_user(owner_id, self.org_id)
        admin_role = _get_builtin_role(self.db, "Admin")

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with (
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            assign_org_role(
                user_id=owner_id,
                body=OrgRoleAssign(role_id=admin_role.id),
                db=self.db,
                current_user=actor,
                _org=None,
            )
        assert exc.value.status_code == 400
        assert "last Owner" in exc.value.detail

    def test_sole_owner_cannot_be_removed(self):
        from rhesis.backend.ee.rbac.router import remove_org_member

        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        actor = _mock_current_user(owner_id, self.org_id)

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with (
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            remove_org_member(
                user_id=owner_id,
                db=self.db,
                current_user=actor,
                _org=None,
            )
        assert exc.value.status_code == 400

    def test_member_assign_rejects_foreign_user(self):
        """User from a different org → 404."""
        from rhesis.backend.ee.rbac.router import assign_org_role
        from rhesis.backend.ee.rbac.schemas import OrgRoleAssign

        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        other_org = _create_org(self.db)
        foreign_user_id = _create_user(self.db, other_org)

        actor = _mock_current_user(owner_id, self.org_id)
        viewer_role = _get_builtin_role(self.db, "Viewer")

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with (
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            assign_org_role(
                user_id=foreign_user_id,
                body=OrgRoleAssign(role_id=viewer_role.id),
                db=self.db,
                current_user=actor,
                _org=None,
            )
        assert exc.value.status_code == 404
        assert "organization" in exc.value.detail.lower()

    def test_multiple_users_multiple_roles_permission_matrix(self):
        """Spot-check a 4-user x 3-permission matrix in one test."""
        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        provider = PermissionAuthorizationProvider()

        roles = ["Owner", "Admin", "Member", "Viewer"]
        users = {}
        for r in roles:
            uid = _create_user(self.db, self.org_id)
            _assign_org_role(self.db, self.org_id, uid, r)
            users[r] = uid

        expected = {
            # (role, permission): expected_result
            ("Owner", "test_set:read"): True,
            ("Owner", "role:manage"): True,
            ("Admin", "test_set:create"): True,
            ("Admin", "role:manage"): False,
            ("Member", "test_set:create"): True,
            ("Member", "member:manage"): False,
            ("Viewer", "test_set:read"): True,
            ("Viewer", "test_set:create"): False,
        }

        with patch.object(provider, "_rbac_available", return_value=True):
            for (role, perm), want in expected.items():
                p = _make_principal(users[role], self.org_id)
                got = _can(provider, p, perm, self.db)
                assert got == want, f"role={role} perm={perm}: expected {want}, got {got}"


# ---------------------------------------------------------------------------
# 5. Project-level assignment API
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestProjectMemberAPI:
    """assign_project_role endpoint — scope guard, membership-required, escalation."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        _do_sync(test_db, ["test_set:read", "test_set:create"])
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)
        self.owner_id = _create_user(test_db, self.org_id)
        _assign_org_role(test_db, self.org_id, self.owner_id, "Owner")
        self.actor = _mock_current_user(self.owner_id, self.org_id)

    def _add_project_member(self, user_id: uuid.UUID, role_name: str | None = None) -> None:
        from rhesis.backend.app.models.project_membership import ProjectMembership

        role_id = None
        if role_name:
            role = _get_builtin_role(self.db, role_name)
            role_id = role.id
        existing = (
            self.db.query(ProjectMembership)
            .filter_by(project_id=self.project_id, user_id=user_id)
            .first()
        )
        if not existing:
            self.db.add(
                ProjectMembership(
                    project_id=self.project_id,
                    user_id=user_id,
                    organization_id=self.org_id,
                    role_id=role_id,
                )
            )
            self.db.flush()

    def test_assign_project_scoped_role_succeeds(self):
        from rhesis.backend.ee.rbac.models import SCOPE_PROJECT, Role
        from rhesis.backend.ee.rbac.router import assign_project_role
        from rhesis.backend.ee.rbac.schemas import ProjectMemberRoleAssign

        # Create a project-scoped custom role.
        custom_role = Role(
            name="ProjReader",
            display_name="Project Reader",
            scope=SCOPE_PROJECT,
            level=50,
            is_built_in=False,
            organization_id=self.org_id,
        )
        self.db.add(custom_role)
        self.db.flush()
        from rhesis.backend.ee.rbac.models import Permission, RolePermission

        perm = self.db.query(Permission).filter_by(name="test_set:read").first()
        if perm:
            self.db.add(RolePermission(role_id=custom_role.id, permission_id=perm.id))
            self.db.flush()

        target_id = _create_user(self.db, self.org_id)
        self._add_project_member(target_id)

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True):
            result = assign_project_role(
                project_id=self.project_id,
                user_id=target_id,
                body=ProjectMemberRoleAssign(role_id=custom_role.id),
                db=self.db,
                current_user=self.actor,
                _org=None,
            )
        assert result.role_id == custom_role.id
        assert result.project_id == self.project_id

    def test_assign_org_scoped_role_to_project_raises_422(self):
        from rhesis.backend.ee.rbac.router import assign_project_role
        from rhesis.backend.ee.rbac.schemas import ProjectMemberRoleAssign

        target_id = _create_user(self.db, self.org_id)
        self._add_project_member(target_id)

        # Built-in "Admin" has scope='organization'.
        admin_role = _get_builtin_role(self.db, "Admin")

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with (
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            assign_project_role(
                project_id=self.project_id,
                user_id=target_id,
                body=ProjectMemberRoleAssign(role_id=admin_role.id),
                db=self.db,
                current_user=self.actor,
                _org=None,
            )
        assert exc.value.status_code == 422

    def test_assign_role_to_non_member_raises_404(self):
        from rhesis.backend.ee.rbac.models import SCOPE_PROJECT, Role
        from rhesis.backend.ee.rbac.router import assign_project_role
        from rhesis.backend.ee.rbac.schemas import ProjectMemberRoleAssign

        custom_role = Role(
            name="ProjRole2",
            scope=SCOPE_PROJECT,
            display_name="",
            level=50,
            is_built_in=False,
            organization_id=self.org_id,
        )
        self.db.add(custom_role)
        self.db.flush()

        non_member_id = _create_user(self.db, self.org_id)

        from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

        with (
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
            pytest.raises(HTTPException) as exc,
        ):
            assign_project_role(
                project_id=self.project_id,
                user_id=non_member_id,
                body=ProjectMemberRoleAssign(role_id=custom_role.id),
                db=self.db,
                current_user=self.actor,
                _org=None,
            )
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
        _do_sync(test_db)
        self.db = test_db
        self.org_id = _create_org(test_db)

    def test_list_members_returns_assigned_users(self):
        from rhesis.backend.ee.rbac.router import list_org_members

        u1 = _create_user(self.db, self.org_id)
        u2 = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, u1, "Admin")
        _assign_org_role(self.db, self.org_id, u2, "Viewer")

        actor = _mock_current_user(u1, self.org_id)
        results = list_org_members(db=self.db, current_user=actor, _org=None)
        user_ids = {r.user_id for r in results}
        assert u1 in user_ids
        assert u2 in user_ids

    def test_list_members_excludes_other_org_users(self):
        from rhesis.backend.ee.rbac.router import list_org_members

        other_org = _create_org(self.db)
        u_mine = _create_user(self.db, self.org_id)
        u_other = _create_user(self.db, other_org)
        _assign_org_role(self.db, self.org_id, u_mine, "Admin")
        _assign_org_role(self.db, other_org, u_other, "Admin")

        actor = _mock_current_user(u_mine, self.org_id)
        results = list_org_members(db=self.db, current_user=actor, _org=None)
        user_ids = {r.user_id for r in results}
        assert u_other not in user_ids


# ---------------------------------------------------------------------------
# 7. Role catalog listing
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestRoleCatalogListing:
    """list_roles returns built-ins + org-owned custom roles, not other orgs'."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        _do_sync(test_db)
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.user_id = _create_user(test_db, self.org_id)
        _assign_org_role(test_db, self.org_id, self.user_id, "Owner")
        self.actor = _mock_current_user(self.user_id, self.org_id)

    def test_list_roles_includes_builtin_roles(self):
        from rhesis.backend.ee.rbac.router import list_roles

        results = list_roles(db=self.db, current_user=self.actor, _org=None)
        names = {r.name for r in results}
        assert {"Owner", "Admin", "Member", "Viewer", "None"} <= names

    def test_list_roles_includes_own_custom_role(self):
        from rhesis.backend.ee.rbac.models import SCOPE_ORGANIZATION, Role

        custom = Role(
            name="OrgCustom",
            display_name="",
            scope=SCOPE_ORGANIZATION,
            level=50,
            is_built_in=False,
            organization_id=self.org_id,
        )
        self.db.add(custom)
        self.db.flush()

        from rhesis.backend.ee.rbac.router import list_roles

        results = list_roles(db=self.db, current_user=self.actor, _org=None)
        names = {r.name for r in results}
        assert "OrgCustom" in names

    def test_list_roles_excludes_other_org_custom_roles(self):
        from rhesis.backend.ee.rbac.models import SCOPE_ORGANIZATION, Role

        other_org = _create_org(self.db)
        foreign = Role(
            name="ForeignRole",
            display_name="",
            scope=SCOPE_ORGANIZATION,
            level=50,
            is_built_in=False,
            organization_id=other_org,
        )
        self.db.add(foreign)
        self.db.flush()

        from rhesis.backend.ee.rbac.router import list_roles

        results = list_roles(db=self.db, current_user=self.actor, _org=None)
        names = {r.name for r in results}
        assert "ForeignRole" not in names


# ---------------------------------------------------------------------------
# 8. FK integrity: project_membership.role_id ON DELETE SET NULL
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestProjectMembershipRoleFK:
    """Verify the FK constraint: deleting a custom role NULLs role_id in project_membership."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        _do_sync(test_db)
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)

    def test_delete_role_nulls_project_membership_role_id(self):
        from rhesis.backend.app.models.project_membership import ProjectMembership
        from rhesis.backend.ee.rbac.models import SCOPE_PROJECT, Role

        custom_role = Role(
            name="TmpProjRole",
            display_name="",
            scope=SCOPE_PROJECT,
            level=50,
            is_built_in=False,
            organization_id=self.org_id,
        )
        self.db.add(custom_role)
        self.db.flush()
        role_id = custom_role.id

        user_id = _create_user(self.db, self.org_id)
        pm = ProjectMembership(
            project_id=self.project_id,
            user_id=user_id,
            organization_id=self.org_id,
            role_id=role_id,
        )
        self.db.add(pm)
        self.db.flush()

        # Delete the role via raw SQL to bypass RESTRICT guards (no org member uses it).
        self.db.execute(text("DELETE FROM role WHERE id = :rid"), {"rid": str(role_id)})
        self.db.flush()

        # The FK ON DELETE SET NULL must have cleared role_id.
        self.db.expire(pm)
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
        from sqlalchemy.exc import IntegrityError

        user_id = _create_user(self.db, self.org_id)
        nonexistent_role_id = uuid.uuid4()

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
                    "rid": str(nonexistent_role_id),
                },
            )
            self.db.flush()
