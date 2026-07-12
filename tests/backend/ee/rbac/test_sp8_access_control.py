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

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.ee.rbac.models import (
    SCOPE_ORGANIZATION,
    SCOPE_PROJECT,
    OrganizationMember,
    Role,
)
from rhesis.backend.ee.rbac.router import (
    _check_escalation,
    assign_org_role,
    assign_project_role,
    check_project_role_assignment,
    create_role,
    delete_role,
    list_org_members,
    list_roles,
    list_user_project_memberships,
    remove_org_member,
    update_role,
)
from rhesis.backend.ee.rbac.schemas import (
    OrgRoleAssign,
    ProjectMemberRoleAssign,
    RoleCreate,
    RoleUpdate,
)
from tests.backend.ee.rbac._rbac_helpers import (
    _add_project_member,
    _assign_org_role,
    _assign_project_role,
    _authorized,
    _builtin_role,
    _create_org,
    _create_project,
    _create_user,
    _custom_role,
    _grant_permission,
    _rbac_enabled,
    _user,
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

    def test_admin_can_read_roles(self):
        # Admin holds role:read (to view the catalog when assigning roles via
        # member:manage); role:manage stays Owner-only.
        assert self._check("Admin", "role:read")

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

    def test_viewer_can_read_project_members(self):
        assert self._check("Viewer", "project_member:read")

    def test_viewer_cannot_manage_project_members(self):
        assert not self._check("Viewer", "project_member:manage")

    def test_viewer_can_read_org_context(self):
        assert self._check("Viewer", "organization:read")
        assert self._check("Viewer", "member:read")

    def test_viewer_cannot_read_sensitive_org_admin(self):
        assert not self._check("Viewer", "role:read")
        assert not self._check("Viewer", "token:read")

    def test_viewer_cannot_request_polyphemus(self):
        assert not self._check("Viewer", "polyphemus:request")

    def test_member_can_request_polyphemus(self):
        assert self._check("Member", "polyphemus:request")

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
    """Project role can elevate but never restrict below the org role (Model A).

    Mirrors GitLab's inherited-membership rule and GCP IAM's resource-hierarchy
    inheritance: a narrower scope (project) can only add to what a broader
    scope (organization) already grants, never take it away.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)
        self.user_id = _create_user(test_db, self.org_id)

    def _can_project(self, perm: str) -> bool:
        return _authorized(self.db, self.user_id, self.org_id, perm, project_id=self.project_id)

    def test_lower_viewer_project_role_does_not_restrict_admin_org_role(self):
        """Admin org role → can create, even with an explicit Viewer project role."""
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        _assign_project_role(self.db, self.org_id, self.project_id, self.user_id, "Viewer")
        assert self._can_project("test_set:create")

    def test_viewer_project_role_still_allows_read(self):
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        _assign_project_role(self.db, self.org_id, self.project_id, self.user_id, "Viewer")
        assert self._can_project("test_set:read")

    def test_none_project_role_does_not_block_admin_org_permissions(self):
        """An explicit None project role can't restrict an Admin org role either."""
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        _assign_project_role(self.db, self.org_id, self.project_id, self.user_id, "None")
        assert self._can_project("test_set:read")

    def test_org_role_applies_when_no_project_role_set(self):
        """Without a project-level row the org role governs."""
        _assign_org_role(self.db, self.org_id, self.user_id, "Admin")
        assert self._can_project("test_set:create")

    def test_higher_project_role_elevates_above_lower_org_role(self):
        """An explicit project role can still elevate access above a lower org role."""
        _assign_org_role(self.db, self.org_id, self.user_id, "Viewer")
        _assign_project_role(self.db, self.org_id, self.project_id, self.user_id, "Owner")
        assert self._can_project("test_set:delete")

    def test_different_users_have_independent_project_roles(self):
        """Two users with the same (low) org role get independent elevation
        from their own explicit project roles."""
        viewer_id = _create_user(self.db, self.org_id)
        member_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, viewer_id, "Viewer")
        _assign_org_role(self.db, self.org_id, member_id, "Viewer")
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

    def test_delete_custom_role_in_use_reassigns_org_holder_to_none(self):
        """Deleting an in-use role no longer 409s — it soft-deletes the role and
        moves org holders to the built-in None role (see test_role_soft_delete.py
        for the full soft-delete behavior)."""
        role_data = self._create(
            RoleCreate(name="InUseRole", scope="organization", permission_names=[])
        )
        target_id = self._assign_member(role_data.id)

        # No longer raises; the holder is reassigned off the deleted role.
        delete_role(role_id=role_data.id, db=self.db, current_user=self.actor, _org=None)

        none_role = _builtin_role(self.db, "None")
        member = (
            self.db.query(OrganizationMember)
            .filter_by(organization_id=self.org_id, user_id=target_id)
            .first()
        )
        assert member is not None
        assert member.role_id == none_role.id

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
        """A self-assign is blocked by the (more general) self-change guard
        before the last-owner check is ever reached — same outcome (denied),
        different reason than the historical "last Owner" message. See
        ``test_self_role_change_denied`` for that guard in isolation and
        ``test_sole_owner_cannot_be_removed`` for the last-owner check, which
        stays reachable via self-*removal* (``remove_org_member`` allows it).
        """
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        with pytest.raises(HTTPException) as exc:
            self._assign(owner_id, owner_id, _builtin_role(self.db, "Admin"))
        assert exc.value.status_code == 400
        assert "own organization role" in exc.value.detail

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

    def test_self_role_change_denied(self):
        """Self-role-change guard applies to any actor, not just Owners."""
        admin_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")

        with pytest.raises(HTTPException) as exc:
            self._assign(admin_id, admin_id, _builtin_role(self.db, "Viewer"))
        assert exc.value.status_code == 400
        assert "own organization role" in exc.value.detail

    def test_admin_cannot_demote_second_owner(self):
        """Regression test for the reported bug: an Admin could freely
        downgrade an Owner's role because the escalation guard only checked
        the *requested* role's level (e.g. Viewer, well within an Admin's
        authority) and never the target's *current* level. An Admin must not
        be able to modify a member who currently outranks them at all,
        regardless of what role is being requested."""
        admin_id = _create_user(self.db, self.org_id)
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        with pytest.raises(HTTPException) as exc:
            self._assign(admin_id, owner_id, _builtin_role(self.db, "Viewer"))
        assert exc.value.status_code == 403
        assert "exceeds your own" in exc.value.detail

    def test_admin_cannot_remove_second_owner(self):
        """Same outranking guard applies to removal, not just role changes."""
        admin_id = _create_user(self.db, self.org_id)
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        with pytest.raises(HTTPException) as exc, _rbac_enabled():
            remove_org_member(
                user_id=owner_id,
                db=self.db,
                current_user=_user(admin_id, self.org_id),
                _org=None,
            )
        assert exc.value.status_code == 403
        assert "exceeds your own" in exc.value.detail

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
# 4b. Escalation guards — _check_escalation / check_project_role_assignment
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestEscalationGuards:
    """Direct unit tests for the privilege-escalation guard (router.py).

    ``_check_escalation`` is a pure function (no DB) — tested directly with
    hand-built inputs. ``check_project_role_assignment`` resolves the actor's
    effective permissions/level from the DB, so those cases use real rows.
    """

    def test_check_escalation_allows_subset_and_equal_level(self):
        _check_escalation(
            permission_names=["test_set:read"],
            role_level=60,
            actor_permissions={"test_set:read", "test_set:create"},
            actor_level=60,
        )  # does not raise

    def test_check_escalation_denies_permission_over_grant(self):
        with pytest.raises(HTTPException) as exc:
            _check_escalation(
                permission_names=["role:manage"],
                role_level=60,
                actor_permissions={"test_set:read"},
                actor_level=80,
            )
        assert exc.value.status_code == 403
        assert "role:manage" in exc.value.detail

    def test_check_escalation_denies_level_above_actor(self):
        with pytest.raises(HTTPException) as exc:
            _check_escalation(
                permission_names=[],
                role_level=100,
                actor_permissions=set(),
                actor_level=80,
            )
        assert exc.value.status_code == 403
        assert "level" in exc.value.detail.lower()

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)

    def test_project_assignment_rejects_unknown_role(self):
        actor_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, actor_id, "Owner")
        with pytest.raises(HTTPException) as exc, _rbac_enabled():
            check_project_role_assignment(
                self.db, _user(actor_id, self.org_id), uuid.uuid4(), self.project_id
            )
        assert exc.value.status_code == 404

    def test_project_assignment_rejects_none_role_at_project_tier(self):
        actor_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, actor_id, "Owner")
        none_role = _builtin_role(self.db, "None")
        with pytest.raises(HTTPException) as exc, _rbac_enabled():
            check_project_role_assignment(
                self.db, _user(actor_id, self.org_id), none_role.id, self.project_id
            )
        assert exc.value.status_code == 422

    def test_project_assignment_allows_owner_role_for_owner_actor(self):
        """Owner (level 100) IS assignable at the project tier (K8s-ClusterRole model)."""
        actor_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, actor_id, "Owner")
        owner_role = _builtin_role(self.db, "Owner")
        with _rbac_enabled():
            resolved = check_project_role_assignment(
                self.db, _user(actor_id, self.org_id), owner_role.id, self.project_id
            )
        assert resolved.id == owner_role.id

    def test_project_assignment_denies_over_privileged_grant(self):
        """A Member actor cannot grant the Owner role at the project tier."""
        actor_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, actor_id, "Member")
        _assign_project_role(self.db, self.org_id, self.project_id, actor_id, "Member")
        owner_role = _builtin_role(self.db, "Owner")
        with pytest.raises(HTTPException) as exc, _rbac_enabled():
            check_project_role_assignment(
                self.db, _user(actor_id, self.org_id), owner_role.id, self.project_id
            )
        assert exc.value.status_code == 403

    def test_project_promotion_does_not_leak_to_other_project(self):
        """Org-level Viewer promoted to Member on one project only stays scoped."""
        user_id = _create_user(self.db, self.org_id)
        other_project_id = _create_project(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, user_id, "Viewer")
        _assign_project_role(self.db, self.org_id, self.project_id, user_id, "Member")

        assert _authorized(
            self.db, user_id, self.org_id, "test_set:create", project_id=self.project_id
        )
        assert not _authorized(
            self.db, user_id, self.org_id, "test_set:create", project_id=other_project_id
        )


# ---------------------------------------------------------------------------
# 4c. Custom-role equal-level escalation guard — _member_permitted_actions
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestCustomRoleEscalationGuard:
    """Every custom role is created at a hardcoded level (50, see
    ``create_role``), decoupled from its permission content — two custom
    roles routinely share a level while holding very different permission
    sets. The level check alone (``current_role_level > actor_level``) is
    not sufficient to authorize modifying/removing such a member:
    ``_member_permitted_actions`` also requires the target's *current*
    custom role's permission set to be a subset of the actor's.
    """

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

    def test_narrow_custom_role_cannot_modify_broader_equal_level_role(self):
        """Actor holds a narrow custom role; target holds an unrelated
        custom role at the *same* level with strictly more permissions.
        The requested new role (None) is well within the actor's authority,
        so only the custom-role subset check can be denying this."""
        narrow_role = _custom_role(self.db, self.org_id, name="Narrow", scope=SCOPE_ORGANIZATION)
        broad_role = _custom_role(self.db, self.org_id, name="Broad", scope=SCOPE_ORGANIZATION)
        _grant_permission(self.db, narrow_role.id, "member:manage")
        _grant_permission(self.db, broad_role.id, "member:manage")
        _grant_permission(self.db, broad_role.id, "role:manage")
        _grant_permission(self.db, broad_role.id, "token:manage")
        assert narrow_role.level == broad_role.level, "both custom roles default to level 50"

        actor_id = _create_user(self.db, self.org_id)
        target_id = _create_user(self.db, self.org_id)
        self.db.add(
            OrganizationMember(
                organization_id=self.org_id, user_id=actor_id, role_id=narrow_role.id
            )
        )
        self.db.add(
            OrganizationMember(
                organization_id=self.org_id, user_id=target_id, role_id=broad_role.id
            )
        )
        self.db.flush()

        with pytest.raises(HTTPException) as exc:
            self._assign(actor_id, target_id, _builtin_role(self.db, "None"))
        assert exc.value.status_code == 403
        assert "exceeds your own" in exc.value.detail

    def test_broad_custom_role_can_modify_narrower_equal_level_role(self):
        """Mirror case: the actor's custom role permissions are a superset
        of the target's — same level, but the modification is allowed."""
        narrow_role = _custom_role(self.db, self.org_id, name="Narrow2", scope=SCOPE_ORGANIZATION)
        broad_role = _custom_role(self.db, self.org_id, name="Broad2", scope=SCOPE_ORGANIZATION)
        _grant_permission(self.db, narrow_role.id, "member:manage")
        _grant_permission(self.db, broad_role.id, "member:manage")
        _grant_permission(self.db, broad_role.id, "role:manage")

        actor_id = _create_user(self.db, self.org_id)
        target_id = _create_user(self.db, self.org_id)
        self.db.add(
            OrganizationMember(organization_id=self.org_id, user_id=actor_id, role_id=broad_role.id)
        )
        self.db.add(
            OrganizationMember(
                organization_id=self.org_id, user_id=target_id, role_id=narrow_role.id
            )
        )
        self.db.flush()

        none_role = _builtin_role(self.db, "None")
        result = self._assign(actor_id, target_id, none_role)
        assert result.role_id == none_role.id


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
        roles bind down to projects.  Only None (level 0) is rejected at the project
        tier; Owner (level 100) is assignable so a project lead can be designated.
        """
        target_id = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, target_id)

        admin_role = _builtin_role(self.db, "Admin")
        result = self._assign(self.project_id, target_id, admin_role)
        assert result.role_id == admin_role.id
        assert result.project_id == self.project_id

    def test_assign_owner_to_project_succeeds(self):
        """Owner (level 100) IS assignable at the project tier.

        A project creator or lead can be designated the project owner
        independently of the org owner. The actor here holds the org Owner
        role, so the escalation guard (role level ≤ actor level, perms ⊆
        actor perms) passes. Only None is rejected at the project tier.
        """
        target_id = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, target_id)

        owner_role = _builtin_role(self.db, "Owner")
        result = self._assign(self.project_id, target_id, owner_role)
        assert result.role_id == owner_role.id
        assert result.project_id == self.project_id

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

    def test_self_project_role_change_denied(self):
        """Self-role-change guard applies at the project tier too."""
        user_id = _create_user(self.db, self.org_id)

        with pytest.raises(HTTPException) as exc, _rbac_enabled():
            assign_project_role(
                project_id=self.project_id,
                user_id=user_id,
                body=ProjectMemberRoleAssign(role_id=_builtin_role(self.db, "Viewer").id),
                db=self.db,
                current_user=_user(user_id, self.org_id),
                _org=None,
            )
        assert exc.value.status_code == 400
        assert "own project role" in exc.value.detail

    def test_project_admin_cannot_change_role_of_project_owner(self):
        """Regression test for the reported bug (screenshot scenario): a
        project Admin could downgrade a project Owner's role, since the
        escalation guard only validated the *requested* role's level (e.g.
        Admin, well within the actor's own authority) and never the
        target's *current* level. A project Admin must not be able to
        modify a member who currently outranks them at the project tier,
        regardless of what role is being requested."""
        admin_id = _create_user(self.db, self.org_id)
        owner_member_id = _create_user(self.db, self.org_id)
        admin_role = _builtin_role(self.db, "Admin")
        owner_role = _builtin_role(self.db, "Owner")
        _add_project_member(self.db, self.org_id, self.project_id, admin_id, admin_role.id)
        _add_project_member(self.db, self.org_id, self.project_id, owner_member_id, owner_role.id)

        with pytest.raises(HTTPException) as exc, _rbac_enabled():
            assign_project_role(
                project_id=self.project_id,
                user_id=owner_member_id,
                body=ProjectMemberRoleAssign(role_id=admin_role.id),
                db=self.db,
                current_user=_user(admin_id, self.org_id),
                _org=None,
            )
        assert exc.value.status_code == 403
        assert "exceeds your own" in exc.value.detail


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
# 6b. permitted_actions field — list_org_members
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestOrgMemberPermittedActions:
    """`permitted_actions` on OrgMemberRead must reflect every escalation
    gate server-side (see `_member_permitted_actions`), so the frontend
    never re-derives self-change / outranking / ambient-permission logic.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)

    def _list(self, actor_id: uuid.UUID):
        with _rbac_enabled():
            return list_org_members(
                db=self.db, current_user=_user(actor_id, self.org_id), _org=None
            )

    def _row(self, results, user_id: uuid.UUID):
        return next(r for r in results if r.user_id == user_id)

    def test_own_row_has_no_permitted_actions(self):
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        results = self._list(owner_id)
        assert self._row(results, owner_id).permitted_actions == []

    def test_admin_sees_manage_and_delete_on_ordinary_member(self):
        admin_id = _create_user(self.db, self.org_id)
        member_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")
        _assign_org_role(self.db, self.org_id, member_id, "Member")

        results = self._list(admin_id)
        actions = self._row(results, member_id).permitted_actions
        assert "member:manage" in actions
        assert "member:delete" in actions

    def test_admin_sees_no_permitted_actions_on_owner_row(self):
        """The core regression, surfaced on the read side too: an Admin
        viewing an Owner's row must not see member:manage, even though
        _check_escalation on the write path would happily let them grant a
        low role — the fix is symmetric across list and write paths."""
        admin_id = _create_user(self.db, self.org_id)
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")

        results = self._list(admin_id)
        assert self._row(results, owner_id).permitted_actions == []

    def test_actor_without_manage_permission_sees_no_actions(self):
        """Ambient-permission gate: even when level and permission-subset
        checks would pass, an actor who doesn't hold member:manage at all
        must not see it in permitted_actions on any row."""
        readonly_role = _custom_role(
            self.db, self.org_id, name="ReadOnlyA", scope=SCOPE_ORGANIZATION
        )
        target_role = _custom_role(self.db, self.org_id, name="ReadOnlyB", scope=SCOPE_ORGANIZATION)
        _grant_permission(self.db, readonly_role.id, "member:read")
        _grant_permission(self.db, target_role.id, "member:read")

        actor_id = _create_user(self.db, self.org_id)
        target_id = _create_user(self.db, self.org_id)
        self.db.add(
            OrganizationMember(
                organization_id=self.org_id, user_id=actor_id, role_id=readonly_role.id
            )
        )
        self.db.add(
            OrganizationMember(
                organization_id=self.org_id, user_id=target_id, role_id=target_role.id
            )
        )
        self.db.flush()

        results = self._list(actor_id)
        assert self._row(results, target_id).permitted_actions == []


# ---------------------------------------------------------------------------
# 6c. Bulk user-project-memberships endpoint (Member Access drawer)
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestListUserProjectMemberships:
    """list_user_project_memberships — single-call replacement for the N
    per-project ``GET /projects/{id}/members`` waterfall the Member Access
    drawer previously required."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)

    def _list(self, target_user_id: uuid.UUID):
        with _rbac_enabled():
            return list_user_project_memberships(
                user_id=target_user_id,
                db=self.db,
                current_user=_user(target_user_id, self.org_id),
                _org=None,
            )

    def test_returns_project_and_role_for_each_membership(self):
        user_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, user_id, "Owner")
        project1 = _create_project(self.db, self.org_id)
        project2 = _create_project(self.db, self.org_id)
        _assign_project_role(self.db, self.org_id, project1, user_id, "Admin")
        _assign_project_role(self.db, self.org_id, project2, user_id, "Viewer")

        results = self._list(user_id)
        by_project = {r.project_id: r for r in results}
        assert by_project[project1].role.name == "Admin"
        assert by_project[project2].role.name == "Viewer"
        assert by_project[project1].project.id == project1

    def test_excludes_other_users_memberships(self):
        user_id = _create_user(self.db, self.org_id)
        other_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, user_id, "Owner")
        project = _create_project(self.db, self.org_id)
        _assign_project_role(self.db, self.org_id, project, user_id, "Admin")
        _assign_project_role(self.db, self.org_id, project, other_id, "Viewer")

        results = self._list(user_id)
        assert {r.user_id for r in results} == {user_id}

    def test_membership_without_role_returns_none_role(self):
        user_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, user_id, "Owner")
        project = _create_project(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, project, user_id)

        results = self._list(user_id)
        assert results[0].role_id is None
        assert results[0].role is None


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
