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
# audit_event is read through the org-scoped audit_log:read, so a reader
# inside a project must still see the whole org's log.
PROJECT_POLICY_EXEMPT_TABLES = frozenset({"project_membership", "audit_event"})


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
        result.setdefault(tablename, []).append({"name": policyname, "permissive": permissive})
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestRLSCoverage:
    """Verify that every tenant-scoped table has correct RLS policies in the DB."""

    def test_tables_with_organization_id_have_rls_enabled(self, test_db):
        """Every table with organization_id must have RLS enabled and forced."""
        tables = _get_tables_with_column(test_db, "organization_id")
        rls_state = _get_rls_state(test_db)

        missing_rls = []
        missing_force = []

        for table in sorted(tables - RLS_EXEMPT_TABLES - TENANT_POLICY_EXEMPT_TABLES):
            state = rls_state.get(table, {})
            if not state.get("rls_enabled"):
                missing_rls.append(table)
            if not state.get("force_rls"):
                missing_force.append(table)

        assert not missing_rls, f"Tables with organization_id missing RLS ENABLED: {missing_rls}"
        assert not missing_force, (
            f"Tables with organization_id missing FORCE ROW LEVEL SECURITY: {missing_force}"
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

        for table in sorted(tables - RLS_EXEMPT_TABLES - PROJECT_POLICY_EXEMPT_TABLES):
            table_policies = {p["name"]: p for p in policies.get(table, [])}
            if "project_isolation" not in table_policies:
                missing.append(table)
            elif table_policies["project_isolation"]["permissive"] != "RESTRICTIVE":
                not_restrictive.append(table)

        assert not missing, f"Tables with project_id missing project_isolation policy: {missing}"
        assert not not_restrictive, (
            f"Tables whose project_isolation policy is not RESTRICTIVE: {not_restrictive}"
        )

    def test_tables_with_project_id_have_rls_enabled(self, test_db):
        """Every table with project_id must have RLS enabled and forced."""
        tables = _get_tables_with_column(test_db, "project_id")
        rls_state = _get_rls_state(test_db)

        missing_rls = []
        missing_force = []

        for table in sorted(tables - RLS_EXEMPT_TABLES):
            state = rls_state.get(table, {})
            if not state.get("rls_enabled"):
                missing_rls.append(table)
            if not state.get("force_rls"):
                missing_force.append(table)

        assert not missing_rls, f"Tables with project_id missing RLS ENABLED: {missing_rls}"
        assert not missing_force, (
            f"Tables with project_id missing FORCE ROW LEVEL SECURITY: {missing_force}"
        )


def _get_views(db) -> dict[str, list[str]]:
    """Return {viewname: reloptions} for every view in the public schema."""
    rows = db.execute(
        text(
            """
            SELECT relname, COALESCE(reloptions, '{}')
            FROM pg_class
            WHERE relnamespace = 'public'::regnamespace
              AND relkind = 'v'
            """
        )
    ).fetchall()
    return {r[0]: list(r[1]) for r in rows}


@pytest.mark.security
class TestViewRLSCoverage:
    """Views run as their owner by default, which skips the RLS of the tables they read."""

    def test_views_run_as_invoker(self, test_db):
        views = _get_views(test_db)
        assert views, "expected the stats views to exist"
        missing = sorted(
            name for name, options in views.items() if "security_invoker=true" not in options
        )
        assert not missing, (
            f"Views without security_invoker = true: {missing}\n"
            "Create views WITH (security_invoker = true) so the underlying tables' "
            "RLS policies apply to the caller, not to the (BYPASSRLS) owner."
        )

    def test_app_role_can_select_views(self, test_db):
        """The app role (NOBYPASSRLS) still has SELECT on every view after recreation."""
        denied = [
            name
            for name in sorted(_get_views(test_db))
            if not test_db.execute(
                text("SELECT has_table_privilege(current_user, :v, 'SELECT')"),
                {"v": f"public.{name}"},
            ).scalar_one()
        ]
        assert not denied, f"App role lacks SELECT on views: {denied}"


# Tables whose tenant_isolation body is deliberately not the canonical one.
NON_CANONICAL_TENANT_POLICIES = frozenset(
    {
        "role",  # built-in roles (organization_id IS NULL) are visible to every org
        "role_permission",  # follows the visibility of its role
        "organization_member",  # also readable with no org bound, to resolve memberships
        "test_set",  # adds the owner-only rule for visibility = 'user'
        "usage",  # NULLIF without the subselect; same rows, evaluated per row
    }
)

# Every table's policy is compared against this one's.
_REFERENCE_TABLE = "test"


def _policy_quals(db, policyname: str) -> dict[str, str]:
    rows = db.execute(
        text(
            "SELECT tablename, qual FROM pg_policies "
            "WHERE schemaname = 'public' AND policyname = :name"
        ),
        {"name": policyname},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


@pytest.mark.security
class TestRLSPolicyBodies:
    """A policy with the right name can still have a body that lets rows through."""

    def test_project_isolation_bodies_are_canonical(self, test_db):
        quals = _policy_quals(test_db, "project_isolation")
        canonical = quals[_REFERENCE_TABLE]
        different = sorted(t for t, q in quals.items() if q != canonical)
        assert not different, (
            f"project_isolation differs from the canonical body on: {different}\n"
            f"Copy the body from b8d2f3e4a5c6:\n{canonical}"
        )

    def test_tenant_isolation_bodies_are_canonical(self, test_db):
        quals = _policy_quals(test_db, "tenant_isolation")
        canonical = quals[_REFERENCE_TABLE]
        exempt = NON_CANONICAL_TENANT_POLICIES | RLS_EXEMPT_TABLES
        different = sorted(t for t, q in quals.items() if q != canonical and t not in exempt)
        assert not different, (
            f"tenant_isolation differs from the canonical body on: {different}\n"
            "Copy the body from f4a91c3e7b52, or list the table in "
            "NON_CANONICAL_TENANT_POLICIES with the reason."
        )

    def test_test_set_policy_has_no_cross_org_branch(self, test_db):
        qual = _policy_quals(test_db, "tenant_isolation")["test_set"]
        assert "public" not in qual
        assert "organization_id" in qual

    @pytest.mark.parametrize("table", ["job", "activity_log"])
    def test_project_rows_hidden_without_a_project(
        self, test_db, test_org_id, authenticated_user_id, table
    ):
        from rhesis.backend.app.models import Project
        from tests.backend.fixtures.rls import as_project, scope_to_org

        scope_to_org(test_db, test_org_id)
        project = Project(
            name="rls body", organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(project)
        test_db.flush()
        columns = {
            "job": "(organization_id, project_id, job_type, status) "
            "VALUES (:org, :project, 'test.job', 'queued')",
            "activity_log": "(organization_id, project_id, level, message) "
            "VALUES (:org, :project, 'info', 'x')",
        }[table]
        params = {"org": test_org_id, "project": str(project.id)}
        with as_project(test_db, project.id):
            row_id = test_db.execute(
                text(f"INSERT INTO {table} {columns} RETURNING id"), params
            ).scalar_one()
            assert test_db.execute(
                text(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": row_id}
            ).first()

        visible = test_db.execute(text(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": row_id})
        assert visible.first() is None
