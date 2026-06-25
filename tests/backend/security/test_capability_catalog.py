"""Drift guard: capability catalog in code must match the permission table.

The ``permission`` table is seeded by Alembic data migrations and is the
authoritative source for custom-role FK targets.  Built-in role permissions
are computed from code, not stored rows, so the table must stay in sync with
what the live route-walk declares.

When this test fails CI prints exactly which capabilities need a new migration:

    Insert into permission table (write a migration):
        ['foo:bar']
    Retire in permission table (write a migration):
        ['old:cap']

Developer contract
------------------
Add or remove a capability (new router, new ``@capability()`` override,
changed HTTP method) → add a follow-up migration:

    # Inserting a new capability:
    op.execute(sa.text(
        "INSERT INTO permission (id, name, display_name, resource_type, action, scope, "
        "is_retired, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'foo:bar', 'Bar foo', 'foo', 'bar', 'project', "
        "false, now(), now()) ON CONFLICT (name) DO NOTHING"
    ))

    # Retiring a removed capability:
    op.execute(sa.text(
        "UPDATE permission SET is_retired = true WHERE name = 'old:cap'"
    ))
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


@pytest.mark.ee
@pytest.mark.integration
@pytest.mark.security
class TestCapabilityCatalogInSync:
    """The permission table must mirror get_all_capabilities() exactly."""

    def test_permission_table_matches_code_catalog(self, test_db: Session) -> None:
        """Fail with actionable diff if catalog drifts from code.

        Compares the non-retired rows in the ``permission`` table against
        the capability list derived from the live route-walk.  Any delta
        means a migration is missing.
        """
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import Permission

        code_caps = set(get_all_capabilities())
        db_caps = {p.name for p in test_db.query(Permission).filter_by(is_retired=False).all()}

        missing = sorted(code_caps - db_caps)
        extra = sorted(db_caps - code_caps)

        assert not missing and not extra, (
            "Capability catalog drifted from the permission table.\n"
            "Write a migration to fix this before merging.\n\n"
            + (
                f"  Insert into permission table (write a migration):\n    {missing}\n"
                if missing
                else ""
            )
            + (f"  Retire in permission table (write a migration):\n    {extra}\n" if extra else "")
        )

    def test_permission_scope_matches_capability_scope(self, test_db: Session) -> None:
        """The seeded ``scope`` column must agree with ``capability_scope()``.

        The drift guard above only checks capability *names*; a migration could
        seed a row with the wrong scope (used by the UI to group permissions).
        This catches that.
        """
        from rhesis.backend.ee.rbac.models import Permission, capability_scope

        mismatches = [
            f"{p.name}: table={p.scope!r} expected={capability_scope(p.name)!r}"
            for p in test_db.query(Permission).filter_by(is_retired=False).all()
            if p.scope != capability_scope(p.name)
        ]
        assert not mismatches, (
            "permission.scope drifted from capability_scope():\n  " + "\n  ".join(mismatches)
        )

    def test_all_five_built_in_roles_exist(self, test_db: Session) -> None:
        """All five built-in roles must be present after migrations."""
        from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_NAMES, Role

        existing = {r.name for r in test_db.query(Role).filter_by(is_built_in=True).all()}
        missing = set(BUILT_IN_ROLE_NAMES) - existing
        assert not missing, f"Missing built-in roles after migrations: {sorted(missing)}"

    def test_built_in_role_levels_correct(self, test_db: Session) -> None:
        """Built-in role levels must match the constants in models.py."""
        from rhesis.backend.ee.rbac.models import BUILT_IN_ROLE_LEVELS, Role

        roles = {r.name: r for r in test_db.query(Role).filter_by(is_built_in=True).all()}
        for name, expected_level in BUILT_IN_ROLE_LEVELS.items():
            assert name in roles, f"Built-in role {name!r} not found"
            assert roles[name].level == expected_level, (
                f"Built-in role {name!r}: expected level {expected_level}, got {roles[name].level}"
            )

    def test_no_role_permission_rows_for_built_ins(self, test_db: Session) -> None:
        """Built-in roles must have no role_permission rows.

        Built-in permissions are computed from code, not stored rows.
        A stale row from a previous sync run would be harmless to authorization
        (the provider ignores the table for built-ins) but signals a dirty DB
        state — the sync removal migration or a manual cleanup is incomplete.
        """
        from rhesis.backend.ee.rbac.models import Role, RolePermission

        built_in_ids = [r.id for r in test_db.query(Role).filter_by(is_built_in=True).all()]
        if not built_in_ids:
            pytest.skip("No built-in roles found — migrations may not have run")

        stale_count = (
            test_db.query(RolePermission).filter(RolePermission.role_id.in_(built_in_ids)).count()
        )
        assert stale_count == 0, (
            f"Found {stale_count} role_permission row(s) for built-in roles. "
            "Built-in permissions are computed from code; these rows are stale. "
            "Run: DELETE FROM role_permission WHERE role_id IN "
            "(SELECT id FROM role WHERE is_built_in = true);"
        )
