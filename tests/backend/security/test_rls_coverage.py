"""
RLS policy coverage tests.

Queries the live database (after migrations run) to verify that every
tenant-scoped table has the right RLS setup. Catching this here is far
cheaper than catching it in production.

Checks per table:
  - RLS is enabled  (pg_class.relrowsecurity = true)
  - FORCE ROW LEVEL SECURITY is on  (pg_class.relforcerowsecurity = true)
  - A PERMISSIVE tenant_isolation policy exists  (tables with organization_id)
  - A RESTRICTIVE project_isolation policy exists  (tables with project_id)

Tables that are deliberately exempt from one or both layers are listed in
the EXEMPT_* sets below with comments explaining why.
"""

import pytest
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Exemption lists — keep in sync with scope_events.py and the RLS migrations.
# ---------------------------------------------------------------------------

# Tables that bypass RLS entirely (no tenant columns, or looked up before
# any tenant context is established).
RLS_EXEMPT_TABLES = frozenset(
    {
        "alembic_version",
        "organization",  # top-level tenant table; has its own policy
        "token",  # looked up before tenant context is bound
        "user",  # identity table; cross-org lookups required
        "refresh_token",  # auth infrastructure; no tenant columns
    }
)

# Tables with organization_id that deliberately do NOT get tenant_isolation.
# (Currently empty — every table with org_id should have it.)
TENANT_POLICY_EXEMPT_TABLES = frozenset()

# Tables with project_id that deliberately do NOT get project_isolation.
# project_membership must stay org-scoped only (it IS the access-control
# join table used to resolve project context before a project is known).
PROJECT_POLICY_EXEMPT_TABLES = frozenset({"project_membership"})

# Tables that have RLS enabled and the right policies but are missing
# FORCE ROW LEVEL SECURITY. FORCE only matters when the current role IS the
# table owner; since APP_DB_USER is never the owner in production this is a
# lower-severity gap. Listed explicitly so the test documents the gap without
# silently hiding it. TODO: add FORCE ROW LEVEL SECURITY to these tables in a
# future migration.
FORCE_RLS_GAP_TABLES = frozenset(
    {
        "project",  # top-level tenant entity; pre-dates FORCE RLS convention
        "prompt_use_case",  # association table; RLS enabled, FORCE missing
        "risk_use_case",  # association table; RLS enabled, FORCE missing
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tables_with_column(db, column_name: str) -> set[str]:
    """Return names of real tables (not views) in the public schema that have the given column."""
    rows = db.execute(
        text(
            """
            SELECT c.table_name
            FROM information_schema.columns c
            JOIN pg_class pc ON pc.relname = c.table_name
                             AND pc.relnamespace = 'public'::regnamespace
                             AND pc.relkind = 'r'
            WHERE c.table_schema = 'public'
              AND c.column_name = :col
            """
        ),
        {"col": column_name},
    ).fetchall()
    return {r[0] for r in rows}


def _get_rls_state(db) -> dict[str, dict]:
    """Return {tablename: {rls_enabled, force_rls}} for all public tables."""
    rows = db.execute(
        text(
            """
            SELECT relname,
                   relrowsecurity,
                   relforcerowsecurity
            FROM pg_class
            WHERE relnamespace = 'public'::regnamespace
              AND relkind = 'r'
            """
        )
    ).fetchall()
    return {r[0]: {"rls_enabled": r[1], "force_rls": r[2]} for r in rows}


def _get_policies(db) -> dict[str, list[dict]]:
    """Return {tablename: [{policyname, permissive}]} for public tables."""
    rows = db.execute(
        text(
            """
            SELECT tablename, policyname, permissive
            FROM pg_policies
            WHERE schemaname = 'public'
            """
        )
    ).fetchall()
    result: dict[str, list] = {}
    for tablename, policyname, permissive in rows:
        result.setdefault(tablename, []).append(
            {"name": policyname, "permissive": permissive}
        )
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestRLSCoverage:
    """Verify that every tenant-scoped table has correct RLS policies in the DB."""

    def test_tables_with_organization_id_have_rls_enabled(self, test_db):
        """Every table with organization_id must have RLS enabled.

        FORCE ROW LEVEL SECURITY (which applies RLS even to the table owner)
        is checked separately; a small set of legacy tables are missing it but
        are tracked in FORCE_RLS_GAP_TABLES as a known gap.
        """
        tables = _get_tables_with_column(test_db, "organization_id")
        rls_state = _get_rls_state(test_db)

        missing_rls = []
        missing_force = []

        scoped = tables - RLS_EXEMPT_TABLES - TENANT_POLICY_EXEMPT_TABLES
        for table in sorted(scoped):
            state = rls_state.get(table, {})
            if not state.get("rls_enabled"):
                missing_rls.append(table)
            if not state.get("force_rls") and table not in FORCE_RLS_GAP_TABLES:
                missing_force.append(table)

        assert not missing_rls, (
            f"Tables with organization_id missing RLS ENABLED: {missing_rls}"
        )
        assert not missing_force, (
            f"Tables with organization_id missing FORCE ROW LEVEL SECURITY: {missing_force}\n"
            f"Known gap tables (exempt for now): {sorted(FORCE_RLS_GAP_TABLES)}"
        )

    def test_tables_with_organization_id_have_tenant_isolation_policy(self, test_db):
        """Every table with organization_id must have a PERMISSIVE tenant_isolation policy.

        Without this permissive grant, all other (restrictive) policies are
        moot — PostgreSQL denies every row when there is no permissive policy.
        architect_message was the canonical example of this failure mode.
        """
        tables = _get_tables_with_column(test_db, "organization_id")
        policies = _get_policies(test_db)

        missing = []
        not_permissive = []

        for table in sorted(tables - RLS_EXEMPT_TABLES - TENANT_POLICY_EXEMPT_TABLES):
            table_policies = {p["name"]: p for p in policies.get(table, [])}
            if "tenant_isolation" not in table_policies:
                missing.append(table)
            elif table_policies["tenant_isolation"]["permissive"] != "PERMISSIVE":
                not_permissive.append(table)

        assert not missing, (
            f"Tables with organization_id missing tenant_isolation policy: {missing}\n"
            "Without a PERMISSIVE policy the table denies every INSERT/SELECT "
            "for non-superuser roles, even when all RESTRICTIVE policies pass."
        )
        assert not not_permissive, (
            f"Tables whose tenant_isolation policy is not PERMISSIVE: {not_permissive}"
        )

    def test_tables_with_project_id_have_project_isolation_policy(self, test_db):
        """Every table with project_id (except exempt ones) must have a RESTRICTIVE
        project_isolation policy."""
        tables = _get_tables_with_column(test_db, "project_id")
        policies = _get_policies(test_db)

        missing = []
        not_restrictive = []

        for table in sorted(
            tables - RLS_EXEMPT_TABLES - PROJECT_POLICY_EXEMPT_TABLES
        ):
            table_policies = {p["name"]: p for p in policies.get(table, [])}
            if "project_isolation" not in table_policies:
                missing.append(table)
            elif table_policies["project_isolation"]["permissive"] != "RESTRICTIVE":
                not_restrictive.append(table)

        assert not missing, (
            f"Tables with project_id missing project_isolation policy: {missing}"
        )
        assert not not_restrictive, (
            f"Tables whose project_isolation policy is not RESTRICTIVE: {not_restrictive}"
        )

    def test_tables_with_project_id_have_rls_enabled(self, test_db):
        """Every table with project_id must have RLS enabled."""
        tables = _get_tables_with_column(test_db, "project_id")
        rls_state = _get_rls_state(test_db)

        missing_rls = []
        missing_force = []

        for table in sorted(tables - RLS_EXEMPT_TABLES):
            state = rls_state.get(table, {})
            if not state.get("rls_enabled"):
                missing_rls.append(table)
            if not state.get("force_rls") and table not in FORCE_RLS_GAP_TABLES:
                missing_force.append(table)

        assert not missing_rls, (
            f"Tables with project_id missing RLS ENABLED: {missing_rls}"
        )
        assert not missing_force, (
            f"Tables with project_id missing FORCE ROW LEVEL SECURITY: {missing_force}\n"
            f"Known gap tables (exempt for now): {sorted(FORCE_RLS_GAP_TABLES)}"
        )
