"""SP7 tests — EE RBAC catalog: tables, seeding, idempotent sync, drift guard.

Exit criteria (plan §SP7):
1. ``permission``, ``role``, ``role_permission``, ``organization_member`` tables exist.
2. ``sync_rbac_catalog`` seeds all five built-in roles with the correct permissions.
3. Running sync twice is idempotent (no duplicate rows, no errors).
4. A new capability added to the registry lands in built-in roles on re-sync, but
   is NOT auto-granted to custom roles (fail-closed).
5. Retiring a capability (removing from registry) sets ``permission.is_retired = True``
   and removes it from built-in role assignments.
6. ``FeatureName.RBAC`` is registered in the EE feature registry.
7. Built-in level rules hold: Owner has all, Viewer has only :read + recycle:view,
   None has nothing, Admin excludes EE management perms.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_sp7_catalog.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.features import FeatureName, FeatureRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _do_sync(db: Session, capabilities: list[str] | None = None) -> None:
    """Run sync_rbac_catalog against a controlled capability list.

    Patches at the source (``capabilities.get_all_capabilities``) because
    ``sync.py`` imports it via a local import inside ``sync_rbac_catalog``.
    """
    from unittest.mock import patch

    from rhesis.backend.ee.rbac.sync import sync_rbac_catalog

    if capabilities is None:
        # Use the live registry (populated from the app routes).
        sync_rbac_catalog(db)
        return

    with patch(
        "rhesis.backend.app.auth.capabilities.get_all_capabilities",
        return_value=capabilities,
    ):
        sync_rbac_catalog(db)


def _permission_names(db: Session) -> set[str]:
    from rhesis.backend.ee.rbac.models import Permission

    return {p.name for p in db.query(Permission).filter_by(is_retired=False).all()}


def _role_permissions(db: Session, role_name: str) -> set[str]:
    from rhesis.backend.ee.rbac.models import Permission, Role, RolePermission

    role = db.query(Role).filter_by(name=role_name, is_built_in=True).first()
    assert role is not None, f"Built-in role {role_name!r} not found"
    return {
        rp.permission.name
        for rp in db.query(RolePermission).filter_by(role_id=role.id).join(Permission).all()
    }


# ---------------------------------------------------------------------------
# Feature registration
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestRbacFeatureRegistration:
    """FeatureName.RBAC must be registered after EE bootstrap."""

    def test_rbac_feature_name_exists(self):
        assert FeatureName.RBAC == "rbac"

    def test_rbac_feature_is_registered(self):
        assert FeatureRegistry.is_registered(FeatureName.RBAC), (
            "FeatureName.RBAC not registered; check ee/__init__.py bootstrap"
        )


# ---------------------------------------------------------------------------
# Table existence
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestRbacTablesExist:
    """All four RBAC tables must exist after migrations."""

    def test_permission_table_exists(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import Permission

        count = test_db.query(Permission).count()
        assert count >= 0  # Table reachable without error

    def test_role_table_exists(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import Role

        count = test_db.query(Role).count()
        assert count >= 0

    def test_role_permission_table_exists(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import RolePermission

        count = test_db.query(RolePermission).count()
        assert count >= 0

    def test_organization_member_table_exists(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import OrganizationMember

        count = test_db.query(OrganizationMember).count()
        assert count >= 0


# ---------------------------------------------------------------------------
# RLS policy shape for built-in roles
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
@pytest.mark.security
class TestBuiltInRoleRLSPolicy:
    """Built-in roles (organization_id IS NULL) must stay globally visible.

    The auto-RLS event trigger installs the standard ``tenant_isolation`` policy
    (``organization_id = current_setting(...)::uuid``) on every table with an
    ``organization_id`` column.  That policy would hide all NULL-org built-in
    roles from any non-superuser (production) connection.  The SP7 migration
    replaces it with a NULL-tolerant policy.

    These guards run against ``pg_policies`` / ``pg_indexes`` directly because
    the normal test DB role is a superuser with BYPASSRLS — it would not surface
    a regression in the policy itself.
    """

    def test_role_tenant_isolation_permits_null_org(self, test_db: Session):
        from sqlalchemy import text

        qual = test_db.execute(
            text(
                "SELECT qual FROM pg_policies "
                "WHERE schemaname='public' AND tablename='role' "
                "AND policyname='tenant_isolation'"
            )
        ).scalar()
        assert qual is not None, "role is missing the tenant_isolation policy"
        normalized = qual.replace(" ", "").lower()
        assert "organization_idisnull" in normalized, (
            "role.tenant_isolation must permit organization_id IS NULL so built-in "
            f"roles stay globally visible; got: {qual!r}"
        )

    def test_role_has_partial_unique_index_on_builtin_name(self, test_db: Session):
        from sqlalchemy import text

        idx = test_db.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND tablename='role' "
                "AND indexname='uq_role_builtin_name'"
            )
        ).scalar()
        assert idx == "uq_role_builtin_name", (
            "role is missing the partial unique index on built-in role names "
            "(name WHERE organization_id IS NULL); duplicate built-ins could slip in "
            "because Postgres treats NULLs as distinct in the composite index"
        )

    def test_restricted_role_sees_builtins_but_not_other_org_custom(
        self, test_db: Session, test_org_id: str
    ):
        """Exercise RLS with a real non-BYPASSRLS role (the production scenario).

        The default test DB role is a superuser with BYPASSRLS, so the rest of
        the suite never actually enforces RLS.  Here we ``SET LOCAL ROLE`` to a
        throwaway NOLOGIN role to prove ``role.tenant_isolation`` keeps built-in
        roles (organization_id IS NULL) globally visible while isolating
        org-owned custom roles.  Everything uses ``SET LOCAL`` and runs inside
        the fixture transaction, so the role and GUCs auto-reset on rollback
        (no pooled-connection leak).
        """
        import uuid

        from sqlalchemy import text

        probe = f"rls_probe_{uuid.uuid4().hex[:8]}"
        other_org = str(uuid.uuid4())

        # Seed a built-in (NULL org) and a custom role owned by the test org.
        # Raw SQL bypasses auto_stamp, so the NULL org_id is preserved.
        test_db.execute(
            text(
                "INSERT INTO role (id,name,scope,level,is_built_in,organization_id) "
                "VALUES (gen_random_uuid(),'ProbeBuiltIn','organization',100,true,NULL)"
            )
        )
        test_db.execute(
            text(
                "INSERT INTO role (id,name,scope,level,is_built_in,organization_id) "
                "VALUES (gen_random_uuid(),'ProbeCustom','project',30,false,:o)"
            ),
            {"o": test_org_id},
        )
        test_db.flush()

        # Throwaway restricted role; SET LOCAL keeps it transaction-scoped.
        test_db.execute(text(f'CREATE ROLE "{probe}" NOLOGIN'))
        test_db.execute(text(f'GRANT SELECT ON public.role TO "{probe}"'))
        test_db.execute(text(f'SET LOCAL ROLE "{probe}"'))

        # A DIFFERENT org in context: only the NULL-org built-in is visible.
        test_db.execute(
            text("SET LOCAL app.current_organization = :o"), {"o": other_org}
        )
        visible = {
            r[0]
            for r in test_db.execute(
                text("SELECT name FROM role WHERE name IN ('ProbeBuiltIn','ProbeCustom')")
            ).fetchall()
        }
        assert "ProbeBuiltIn" in visible, (
            "built-in role hidden under RLS — the tenant_isolation policy is "
            "missing its 'organization_id IS NULL' clause"
        )
        assert "ProbeCustom" not in visible, (
            "a custom role from another org leaked under RLS"
        )

        # The owning org in context: both the built-in and own custom are visible.
        test_db.execute(
            text("SET LOCAL app.current_organization = :o"), {"o": test_org_id}
        )
        visible_owner = {
            r[0]
            for r in test_db.execute(
                text("SELECT name FROM role WHERE name IN ('ProbeBuiltIn','ProbeCustom')")
            ).fetchall()
        }
        assert visible_owner == {"ProbeBuiltIn", "ProbeCustom"}


# ---------------------------------------------------------------------------
# Idempotent sync
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestSyncIdempotent:
    """Running sync twice must produce the same DB state."""

    _CAPS = [
        "test_set:read",
        "test_set:create",
        "test_set:update",
        "test_set:delete",
        "test_set:execute",
        "test:read",
        "test:create",
        "organization:update",
        "member:manage",
        "recycle:view",
        "recycle:restore",
        "role:manage",
        "role:read",
    ]

    def test_sync_twice_same_permission_count(self, test_db: Session):
        _do_sync(test_db, self._CAPS)
        first_count = test_db.query(__import__(
            "rhesis.backend.ee.rbac.models", fromlist=["Permission"]
        ).Permission).filter_by(is_retired=False).count()

        _do_sync(test_db, self._CAPS)
        second_count = test_db.query(__import__(
            "rhesis.backend.ee.rbac.models", fromlist=["Permission"]
        ).Permission).filter_by(is_retired=False).count()

        assert first_count == second_count

    def test_sync_twice_same_role_count(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_NAMES, Role

        _do_sync(test_db, self._CAPS)
        _do_sync(test_db, self._CAPS)

        count = test_db.query(Role).filter_by(is_built_in=True).count()
        assert count == len(BUILT_IN_ROLE_NAMES), (
            f"Expected {len(BUILT_IN_ROLE_NAMES)} built-in roles, got {count}"
        )

    def test_sync_twice_no_duplicate_role_permissions(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import RolePermission
        from sqlalchemy import func

        _do_sync(test_db, self._CAPS)
        _do_sync(test_db, self._CAPS)

        duplicates = (
            test_db.query(RolePermission.role_id, RolePermission.permission_id)
            .group_by(RolePermission.role_id, RolePermission.permission_id)
            .having(func.count() > 1)
            .count()
        )
        assert duplicates == 0, "Duplicate role_permission rows found after double-sync"


# ---------------------------------------------------------------------------
# Built-in role level rules
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestBuiltInRoleLevelRules:
    """Verify the permission sets for each built-in role (plan §2.2)."""

    _CAPS = [
        "test_set:read",
        "test_set:create",
        "test_set:update",
        "test_set:delete",
        "test_set:execute",
        "test_set:generate",
        "test:read",
        "test:create",
        "test:update",
        "test:delete",
        "test_run:read",
        "test_run:execute",
        "experiment:read",
        "experiment:create",
        "organization:read",
        "organization:update",
        "member:read",
        "member:manage",
        "member:update",
        "recycle:view",
        "recycle:restore",
        "recycle:purge",
        "role:read",
        "role:manage",
        "sso:manage",
        "api_clients:manage",
        "file:read",
        "file:import",
        "comment:read",
        "comment:create",
        "comment:react",
    ]

    def _sync_and_get(self, test_db: Session) -> None:
        _do_sync(test_db, self._CAPS)

    def test_owner_has_all_permissions(self, test_db: Session):
        self._sync_and_get(test_db)
        owner_perms = _role_permissions(test_db, "Owner")
        assert owner_perms == set(self._CAPS), (
            f"Owner missing: {set(self._CAPS) - owner_perms}; "
            f"extra: {owner_perms - set(self._CAPS)}"
        )

    def test_none_has_no_permissions(self, test_db: Session):
        self._sync_and_get(test_db)
        none_perms = _role_permissions(test_db, "None")
        assert none_perms == set(), f"None role should have 0 permissions, got: {none_perms}"

    def test_viewer_has_only_read_and_recycle_view(self, test_db: Session):
        self._sync_and_get(test_db)
        viewer_perms = _role_permissions(test_db, "Viewer")
        for perm in viewer_perms:
            assert perm.endswith(":read") or perm == "recycle:view", (
                f"Viewer should only have :read perms + recycle:view, got: {perm!r}"
            )
        # Viewer must have all :read capabilities
        read_caps = {c for c in self._CAPS if c.endswith(":read")}
        assert read_caps.issubset(viewer_perms), (
            f"Viewer missing read caps: {read_caps - viewer_perms}"
        )

    def test_admin_excludes_ee_management_perms(self, test_db: Session):
        self._sync_and_get(test_db)
        admin_perms = _role_permissions(test_db, "Admin")
        excluded = {"role:manage", "role:read", "sso:manage", "api_clients:manage"}
        overlap = admin_perms & excluded
        assert not overlap, (
            f"Admin role should not include EE management permissions, found: {overlap}"
        )

    def test_admin_has_most_permissions(self, test_db: Session):
        self._sync_and_get(test_db)
        admin_perms = _role_permissions(test_db, "Admin")
        owner_perms = _role_permissions(test_db, "Owner")
        # Admin is a strict subset of Owner
        assert admin_perms < owner_perms, "Admin should be a strict subset of Owner"

    def test_member_has_only_project_scoped_permissions(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import capability_scope, SCOPE_PROJECT

        self._sync_and_get(test_db)
        member_perms = _role_permissions(test_db, "Member")
        for perm in member_perms:
            assert capability_scope(perm) == SCOPE_PROJECT, (
                f"Member should only have project-scoped permissions, got: {perm!r} "
                f"(scope={capability_scope(perm)!r})"
            )

    def test_member_does_not_have_recycle_or_org_admin(self, test_db: Session):
        self._sync_and_get(test_db)
        member_perms = _role_permissions(test_db, "Member")
        org_only = {"organization:update", "member:manage", "recycle:restore", "recycle:purge"}
        overlap = member_perms & org_only
        assert not overlap, (
            f"Member should not have org-admin capabilities, found: {overlap}"
        )

    def test_role_levels_are_ordered(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_LEVELS, Role

        self._sync_and_get(test_db)
        roles = {r.name: r for r in test_db.query(Role).filter_by(is_built_in=True).all()}
        for name, expected_level in BUILT_IN_ROLE_LEVELS.items():
            assert roles[name].level == expected_level, (
                f"Role {name!r} level: expected {expected_level}, got {roles[name].level}"
            )


# ---------------------------------------------------------------------------
# New capability fail-closed for custom roles
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestNewCapabilityFailClosed:
    """New capabilities must NOT be auto-granted to custom roles."""

    def test_new_cap_not_granted_to_custom_role(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import (
            OrganizationMember,
            Permission,
            Role,
            RolePermission,
        )

        initial_caps = ["test_set:read", "test_set:create"]
        _do_sync(test_db, initial_caps)

        # Create a custom role and grant it the initial capabilities.
        custom_role = Role(
            name="CustomReader",
            display_name="Custom Reader",
            scope="project",
            level=30,
            is_built_in=False,
            organization_id=None,  # NULL simulates an org custom role for test simplicity
        )
        test_db.add(custom_role)
        test_db.flush()
        test_db.refresh(custom_role)

        perms = test_db.query(Permission).filter(
            Permission.name.in_(initial_caps)
        ).all()
        for perm in perms:
            test_db.add(RolePermission(role_id=custom_role.id, permission_id=perm.id))
        test_db.flush()

        # Add a new capability and re-sync.
        new_caps = initial_caps + ["test_set:delete"]
        _do_sync(test_db, new_caps)

        # Built-in roles got the new capability.
        owner_perms = _role_permissions(test_db, "Owner")
        assert "test_set:delete" in owner_perms, "Owner should have new cap after re-sync"

        # Custom role was NOT modified.
        custom_rp_names = {
            rp.permission.name
            for rp in test_db.query(RolePermission)
            .filter_by(role_id=custom_role.id)
            .join(Permission)
            .all()
        }
        assert "test_set:delete" not in custom_rp_names, (
            "New capability was auto-granted to custom role — fail-closed invariant violated"
        )


# ---------------------------------------------------------------------------
# Capability retirement
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestCapabilityRetirement:
    """Capabilities removed from the registry are retired, not deleted."""

    def test_removed_cap_is_retired_not_deleted(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import Permission

        caps_v1 = ["test_set:read", "test_set:create", "test_set:update"]
        _do_sync(test_db, caps_v1)

        # Remove one capability from the registry.
        caps_v2 = ["test_set:read", "test_set:create"]
        _do_sync(test_db, caps_v2)

        perm = test_db.query(Permission).filter_by(name="test_set:update").first()
        assert perm is not None, "Retired permission row should still exist"
        assert perm.is_retired is True, "Removed capability should be marked is_retired=True"

    def test_retired_cap_not_in_built_in_roles(self, test_db: Session):
        caps_v1 = ["test_set:read", "test_set:create", "test_set:update"]
        _do_sync(test_db, caps_v1)

        caps_v2 = ["test_set:read", "test_set:create"]
        _do_sync(test_db, caps_v2)

        for role_name in ("Owner", "Admin", "Member", "Viewer"):
            perms = _role_permissions(test_db, role_name)
            assert "test_set:update" not in perms, (
                f"Retired capability still in built-in role {role_name!r}"
            )

    def test_revived_cap_is_un_retired(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import Permission

        caps_v1 = ["test_set:read", "test_set:create"]
        _do_sync(test_db, caps_v1)

        caps_v2 = ["test_set:read"]  # retire test_set:create
        _do_sync(test_db, caps_v2)

        perm = test_db.query(Permission).filter_by(name="test_set:create").first()
        assert perm.is_retired is True

        # Bring it back.
        caps_v3 = ["test_set:read", "test_set:create"]
        _do_sync(test_db, caps_v3)

        test_db.refresh(perm)
        assert perm.is_retired is False, "Re-added capability should clear is_retired flag"


# ---------------------------------------------------------------------------
# permissions_for_built_in_role unit tests (pure, no DB)
# ---------------------------------------------------------------------------


class TestPermissionsForBuiltInRole:
    """Unit tests for the level-rule function (no DB needed)."""

    _CAPS = [
        "test_set:read",
        "test_set:create",
        "test_set:execute",
        "organization:update",
        "member:manage",
        "recycle:view",
        "recycle:restore",
        "role:manage",
        "role:read",
        "sso:manage",
        "api_clients:manage",
        "comment:react",
        "file:import",
    ]

    def test_owner_gets_everything(self):
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        result = permissions_for_built_in_role("Owner", self._CAPS)
        assert result == set(self._CAPS)

    def test_none_gets_nothing(self):
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        result = permissions_for_built_in_role("None", self._CAPS)
        assert result == set()

    def test_unknown_role_gets_nothing(self):
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        result = permissions_for_built_in_role("Superuser", self._CAPS)
        assert result == set()

    def test_viewer_only_read_and_recycle_view(self):
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        result = permissions_for_built_in_role("Viewer", self._CAPS)
        assert "test_set:read" in result
        assert "recycle:view" in result
        assert "test_set:create" not in result
        assert "organization:update" not in result
        assert "member:manage" not in result

    def test_admin_excludes_ee_management(self):
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        result = permissions_for_built_in_role("Admin", self._CAPS)
        assert "role:manage" not in result
        assert "role:read" not in result
        assert "sso:manage" not in result
        assert "api_clients:manage" not in result
        assert "organization:update" in result  # Admin CAN update org
        assert "member:manage" in result  # Admin CAN manage members

    def test_member_project_scoped_only(self):
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        result = permissions_for_built_in_role("Member", self._CAPS)
        assert "test_set:read" in result
        assert "test_set:create" in result
        assert "test_set:execute" in result
        assert "comment:react" in result
        assert "file:import" in result
        assert "organization:update" not in result
        assert "member:manage" not in result
        assert "recycle:restore" not in result
        assert "role:manage" not in result

    def test_member_allowlist_is_subset_of_project_scope(self):
        """Every resource in the Member allowlist must be project-scoped.

        Guards the documented invariant in models.py: ``_PROJECT_SCOPED_RESOURCES``
        ⊆ {resources where ``capability_scope`` returns ``project``}.  If a resource
        is added to the allowlist but is actually org-scoped, this catches it.
        """
        from rhesis.backend.ee.rbac.models import (
            SCOPE_PROJECT,
            _PROJECT_SCOPED_RESOURCES,
            capability_scope,
        )

        misclassified = [
            resource
            for resource in _PROJECT_SCOPED_RESOURCES
            if capability_scope(f"{resource}:read") != SCOPE_PROJECT
        ]
        assert not misclassified, (
            f"Resources in _PROJECT_SCOPED_RESOURCES that capability_scope does not "
            f"classify as project-scoped: {misclassified}"
        )
