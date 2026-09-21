"""Guard tenant_isolation policies against a blank org GUC, drop a broken policy

Two RLS problems, both invisible until the test suite stopped running as a
BYPASSRLS superuser (issue #2525).

1. 38 ``tenant_isolation`` policies cast the org GUC straight to uuid:

       organization_id = (SELECT current_setting('app.current_organization')::uuid)

   When the GUC is blank -- which happens after ``reset_session_context`` and
   on any path that reaches the DB before tenant vars are bound -- ``''::uuid``
   raises ``invalid input syntax for type uuid`` and the request 500s instead
   of returning zero rows. NULLIF turns a blank into NULL so the comparison is
   NULL (not true) and the row is denied. Deny, don't crash.

   The ``(SELECT ...)`` wrapper is kept: it makes Postgres evaluate the GUC
   once as an InitPlan rather than per row (see b8d2f3e4a5c6).

2. ``test_set_metric_organization_isolation`` reads ``app.organization_id``,
   a GUC this codebase never sets, so its ``IS NULL`` branch is always true.
   Permissive policies are ORed, so that one policy cancelled the table's real
   ``tenant_isolation`` and left org isolation unenforced. Dropped; the
   guarded ``tenant_isolation`` and restrictive ``project_isolation`` already
   cover the table.

Revision ID: f4a91c3e7b52
Revises: b6723e65f233
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f4a91c3e7b52"
down_revision: Union[str, None] = "b6723e65f233"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Matches only the unguarded org-scoped policies: skips the organization table
# (keys off `id`, already guarded by a CASE) and anything already using NULLIF
# or a CASE guard.
_UNGUARDED = """
    SELECT tablename
    FROM pg_policies
    WHERE schemaname = 'public'
      AND policyname = 'tenant_isolation'
      AND qual LIKE '%organization_id%'
      AND qual LIKE '%app.current_organization%'
      AND qual NOT LIKE '%NULLIF%'
      AND qual NOT LIKE '%CASE%'
"""


def upgrade() -> None:
    op.execute(f"""
    DO $$
    DECLARE r RECORD;
    BEGIN
        FOR r IN {_UNGUARDED}
        LOOP
            EXECUTE format('DROP POLICY tenant_isolation ON public.%I', r.tablename);
            EXECUTE format(
                'CREATE POLICY tenant_isolation ON public.%I AS PERMISSIVE FOR ALL TO public '
                'USING (organization_id = (SELECT NULLIF('
                'current_setting(''app.current_organization'', true), '''')::uuid))',
                r.tablename
            );
        END LOOP;
    END;
    $$;
    """)

    op.execute("DROP POLICY IF EXISTS test_set_metric_organization_isolation ON test_set_metric")


def downgrade() -> None:
    # The NULLIF guard is deliberately not reverted. Several tables already used
    # NULLIF before this migration, and nothing in pg_policies distinguishes those
    # from the ones changed here, so a blanket revert would un-guard them too.
    # Reverting would only restore a crash (''::uuid) with no behavioural gain.
    op.execute("""
        CREATE POLICY test_set_metric_organization_isolation ON test_set_metric
        FOR ALL
        USING (
            organization_id::text = current_setting('app.organization_id', true)
            OR current_setting('app.organization_id', true) IS NULL
            OR current_setting('app.organization_id', true) = ''
        )
    """)
