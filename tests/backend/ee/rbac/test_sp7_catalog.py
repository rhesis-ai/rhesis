"""SP7 tests — EE RBAC catalog: tables, migrations, and role-level rules.

Exit criteria (updated after sync removal):
1. ``permission``, ``role``, ``role_permission``, ``organization_member`` tables exist.
2. All five built-in roles are seeded by migrations with correct levels.
3. No ``role_permission`` rows exist for built-in roles (permissions computed from code).
4. ``FeatureName.RBAC`` is registered in the EE feature registry.
5. Built-in level rules hold: Owner has all, Viewer has :read (minus sensitive
   org-admin reads) + recycle:view, None has nothing, Admin excludes EE
   management perms — verified from code, not DB.
6. RLS policy on ``role`` permits NULL-org built-ins globally.
7. Built-in roles nest monotonically (Owner ⊇ Admin ⊇ Member ⊇ Viewer ⊇ None)
   and Member covers every project-scoped resource.

Note: sync-based tests (idempotent sync, retirement, revival) are removed.
The catalog is now migration-managed.  See test_capability_catalog.py for the
drift guard that enforces code ↔ DB consistency.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_sp7_catalog.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.features import FeatureName, FeatureRegistry

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

        assert test_db.query(Permission).count() >= 0

    def test_role_table_exists(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import Role

        assert test_db.query(Role).count() >= 0

    def test_role_permission_table_exists(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import RolePermission

        assert test_db.query(RolePermission).count() >= 0

    def test_organization_member_table_exists(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import OrganizationMember

        assert test_db.query(OrganizationMember).count() >= 0


# ---------------------------------------------------------------------------
# Built-in role seeding
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestBuiltInRoleSeeding:
    """All five built-in roles must be present and correctly configured."""

    def test_all_built_in_roles_exist(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_NAMES, Role

        existing = {r.name for r in test_db.query(Role).filter_by(is_built_in=True).all()}
        assert set(BUILT_IN_ROLE_NAMES) == existing, (
            f"Missing built-in roles: {set(BUILT_IN_ROLE_NAMES) - existing}"
        )

    def test_built_in_roles_have_null_organization_id(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_NAMES, Role

        for name in BUILT_IN_ROLE_NAMES:
            role = test_db.query(Role).filter_by(name=name, is_built_in=True).first()
            assert role is not None, f"Built-in role {name!r} not found"
            assert role.organization_id is None, (
                f"Built-in role {name!r} must have organization_id=NULL"
            )

    def test_built_in_role_levels(self, test_db: Session):
        from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_LEVELS, Role

        roles = {r.name: r for r in test_db.query(Role).filter_by(is_built_in=True).all()}
        for name, expected in BUILT_IN_ROLE_LEVELS.items():
            assert roles[name].level == expected, (
                f"Role {name!r}: expected level {expected}, got {roles[name].level}"
            )

    def test_no_role_permission_rows_for_built_ins(self, test_db: Session):
        """Built-in roles must have no stored role_permission rows.

        Their permissions are computed from code via permissions_for_built_in_role,
        so stored rows would be stale/misleading.
        """
        from rhesis.backend.ee.rbac.models import Role, RolePermission

        built_in_ids = [r.id for r in test_db.query(Role).filter_by(is_built_in=True).all()]
        count = (
            test_db.query(RolePermission).filter(RolePermission.role_id.in_(built_in_ids)).count()
        )
        assert count == 0, (
            f"Found {count} role_permission row(s) for built-in roles — "
            "built-in permissions are computed from code, not stored rows"
        )


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
            "(name WHERE organization_id IS NULL)"
        )

    def test_restricted_role_sees_builtins_but_not_other_org_custom(
        self, test_db: Session, test_org_id: str
    ):
        """Exercise RLS with a real non-BYPASSRLS role (the production scenario)."""
        import uuid

        from sqlalchemy import text

        probe = f"rls_probe_{uuid.uuid4().hex[:8]}"
        other_org = str(uuid.uuid4())

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

        test_db.execute(text(f'CREATE ROLE "{probe}" NOLOGIN'))
        test_db.execute(text(f'GRANT SELECT ON public.role TO "{probe}"'))
        test_db.execute(text(f'SET LOCAL ROLE "{probe}"'))

        test_db.execute(text("SET LOCAL app.current_organization = :o"), {"o": other_org})
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
        assert "ProbeCustom" not in visible, "a custom role from another org leaked under RLS"

        test_db.execute(text("SET LOCAL app.current_organization = :o"), {"o": test_org_id})
        visible_owner = {
            r[0]
            for r in test_db.execute(
                text("SELECT name FROM role WHERE name IN ('ProbeBuiltIn','ProbeCustom')")
            ).fetchall()
        }
        assert visible_owner == {"ProbeBuiltIn", "ProbeCustom"}

    def test_restricted_role_cannot_write_builtin_or_cross_org(
        self, test_db: Session, test_org_id: str
    ):
        """Audit fix: the role WITH CHECK must let a tenant write only its own-org
        rows — never a NULL-org (built-in) or cross-org role row."""
        import uuid

        import pytest
        from sqlalchemy import text

        probe = f"rls_wc_probe_{uuid.uuid4().hex[:8]}"
        other_org = str(uuid.uuid4())

        test_db.execute(text(f'CREATE ROLE "{probe}" NOLOGIN'))
        test_db.execute(text(f'GRANT SELECT, INSERT ON public.role TO "{probe}"'))
        test_db.execute(text(f'SET LOCAL ROLE "{probe}"'))
        test_db.execute(text("SET LOCAL app.current_organization = :o"), {"o": test_org_id})

        # Own-org custom role: permitted by WITH CHECK.
        with test_db.begin_nested():
            test_db.execute(
                text(
                    "INSERT INTO role (id,name,scope,level,is_built_in,organization_id) "
                    "VALUES (gen_random_uuid(),'WcOwnOrg','project',30,false,:o)"
                ),
                {"o": test_org_id},
            )

        # NULL-org (built-in) row: rejected — a tenant must not mint a global role.
        with pytest.raises(Exception):
            with test_db.begin_nested():
                test_db.execute(
                    text(
                        "INSERT INTO role (id,name,scope,level,is_built_in,organization_id) "
                        "VALUES (gen_random_uuid(),'WcEvilBuiltIn','organization',100,true,NULL)"
                    )
                )

        # Cross-org row: rejected.
        with pytest.raises(Exception):
            with test_db.begin_nested():
                test_db.execute(
                    text(
                        "INSERT INTO role (id,name,scope,level,is_built_in,organization_id) "
                        "VALUES (gen_random_uuid(),'WcCrossOrg','project',30,false,:o)"
                    ),
                    {"o": other_org},
                )

        test_db.execute(text("RESET ROLE"))


# ---------------------------------------------------------------------------
# permissions_for_built_in_role unit tests (pure, no DB)
# ---------------------------------------------------------------------------


class TestPermissionsForBuiltInRole:
    """Unit tests for the level-rule function (no DB needed).

    These verify that the code function that drives built-in authorization
    correctly implements the allowlist rules — independent of any DB state.
    """

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

    def test_architect_create_is_member_not_viewer(self):
        """SP11 gate semantics: a read-only Viewer may read but not run the
        architect agent; a Member may run it (and preflight)."""
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        caps = ["architect:read", "architect:create", "preflight:create", "test_set:read"]
        viewer = permissions_for_built_in_role("Viewer", caps)
        member = permissions_for_built_in_role("Member", caps)

        assert "architect:read" in viewer
        assert "architect:create" not in viewer
        assert "preflight:create" not in viewer
        assert {"architect:read", "architect:create", "preflight:create"} <= member

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
        # role:read IS granted to Admin so they can see the role catalog when
        # assigning roles via member:manage; only role:manage stays Owner-only.
        assert "role:read" in result
        assert "sso:manage" not in result
        assert "api_clients:manage" not in result
        assert "organization:update" in result
        assert "member:manage" in result

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

    def test_viewer_excludes_sensitive_org_reads(self):
        """Viewer gets org-context reads but never role:read / token:read."""
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        caps = [
            "test_set:read",
            "organization:read",
            "member:read",
            "role:read",
            "token:read",
            "recycle:view",
        ]
        viewer = permissions_for_built_in_role("Viewer", caps)
        assert "organization:read" in viewer
        assert "member:read" in viewer
        assert "recycle:view" in viewer
        assert "role:read" not in viewer
        assert "token:read" not in viewer

    def test_member_covers_all_project_resources(self):
        """Member must hold CRUD on every project-scoped resource, not an allowlist."""
        from rhesis.backend.ee.rbac.models import (
            SCOPE_PROJECT,
            capability_scope,
            permissions_for_built_in_role,
        )

        caps = [
            "behavior:read",
            "behavior:create",
            "topic:update",
            "category:delete",
            "test_set:read",
            "organization:update",  # org-scoped → Member must NOT get it
        ]
        member = permissions_for_built_in_role("Member", caps)
        project_crud = {c for c in caps if capability_scope(c) == SCOPE_PROJECT}
        assert project_crud <= member, f"Member missing project caps: {project_crud - member}"
        assert "organization:update" not in member

    def test_built_in_roles_nest_monotonically(self):
        """Owner ⊇ Admin ⊇ Member ⊇ Viewer ⊇ None against the live catalog."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        caps = get_all_capabilities()
        owner = permissions_for_built_in_role("Owner", caps)
        admin = permissions_for_built_in_role("Admin", caps)
        member = permissions_for_built_in_role("Member", caps)
        viewer = permissions_for_built_in_role("Viewer", caps)
        none = permissions_for_built_in_role("None", caps)

        assert none <= viewer, f"None ⊄ Viewer: {none - viewer}"
        assert viewer <= member, f"Viewer ⊄ Member: {viewer - member}"
        assert member <= admin, f"Member ⊄ Admin: {member - admin}"
        assert admin <= owner, f"Admin ⊄ Owner: {admin - owner}"

    def test_member_reads_superset_of_viewer_reads_live(self):
        """Regression for the SP8 inversion: a Member must read everything a
        Viewer can read against the real 49-resource catalog."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        caps = get_all_capabilities()
        member = permissions_for_built_in_role("Member", caps)
        viewer = permissions_for_built_in_role("Viewer", caps)
        viewer_reads = {c for c in viewer if c.endswith(":read")}
        missing = viewer_reads - member
        assert not missing, f"Member cannot read what Viewer can: {sorted(missing)}"

    def test_owner_level_rules_hold_against_live_catalog(self):
        """Owner must hold every capability in the live route-walk catalog."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        all_caps = get_all_capabilities()
        owner_perms = permissions_for_built_in_role("Owner", all_caps)
        assert owner_perms == set(all_caps), (
            f"Owner missing from live catalog: {set(all_caps) - owner_perms}"
        )

    def test_none_has_no_permissions_against_live_catalog(self):
        """None role must hold zero permissions regardless of catalog size."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        result = permissions_for_built_in_role("None", get_all_capabilities())
        assert result == set()

    def test_admin_excludes_ee_management_against_live_catalog(self):
        """Admin must never hold EE-management caps regardless of catalog changes.

        role:read is intentionally NOT excluded — Admin can view the role
        catalog (to assign roles via member:manage); only role:manage,
        sso:manage, and api_clients:manage stay Owner-only.
        """
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        admin = permissions_for_built_in_role("Admin", get_all_capabilities())
        excluded = {"role:manage", "sso:manage", "api_clients:manage"}
        assert not admin & excluded, (
            f"Admin role holds EE-only management permissions: {admin & excluded}"
        )
