"""Evaluate the RLS policy GUC lookups once per query

``current_setting()`` in a policy's USING clause is a STABLE function call in
a filter expression, so Postgres runs it for every row the scan visits.
Wrapping it as ``(SELECT current_setting(...))`` turns it into an InitPlan the
planner runs once per query.

The tenant_isolation lookup was already hoisted whenever the query also
carries ``organization_id = :org`` - the scope listener always adds that, and
the plan shows it as a One-Time Filter. The two project_isolation lookups were
not: they stayed in the per-row Filter on every plan measured.

Measured after a7c1e2d3f4b5, on Postgres 16 with 50,000 prompt rows across 3
organizations, as a non-BYPASSRLS role with the tenant GUCs set the way
``get_db_with_tenant_variables`` sets them (median of 25 runs):

                                        before   after
    list page, org scope only           0.78 ms  0.28 ms
    list page, org + active project     4.05 ms  2.47 ms
    count over one org's rows           5.96 ms  2.23 ms

Only the two canonical policy bodies are rewritten (37 tenant_isolation, 35
project_isolation). Tables with their own policy shape (organization,
test_set, role, role_permission, organization_member, activity_log, job,
usage) are left alone. ``auto_apply_rls_policies()`` is updated to the same
form so any table it ever covers gets it too.

Revision ID: b8d2f3e4a5c6
Revises: a7c1e2d3f4b5
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b8d2f3e4a5c6"
down_revision: Union[str, None] = "a7c1e2d3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables carrying the canonical tenant_isolation body
# ``organization_id = current_setting('app.current_organization')::uuid``.
_TENANT_ISOLATION_TABLES = [
    "architect_message",
    "architect_session",
    "auth_client",
    "category",
    "chunk",
    "comment",
    "embedding",
    "endpoint",
    "execution_trace",
    "experiment",
    "file",
    "metric",
    "model",
    "notification",
    "project",
    "project_membership",
    "prompt",
    "prompt_template",
    "prompt_test_set",
    "requirement",
    "requirement_metric",
    "source",
    "status",
    "subscription",
    "tag",
    "tagged_item",
    "task",
    "test",
    "test_configuration",
    "test_result",
    "test_run",
    "test_set_metric",
    "test_test_set",
    "tool",
    "topic",
    "trace",
    "type_lookup",
]

# Tables carrying the fail-closed project_isolation body from b8c9d0e1f2a3.
_PROJECT_ISOLATION_TABLES = [
    "architect_message",
    "architect_session",
    "category",
    "chunk",
    "comment",
    "embedding",
    "endpoint",
    "execution_trace",
    "experiment",
    "file",
    "metric",
    "model",
    "notification",
    "prompt",
    "prompt_template",
    "prompt_test_set",
    "requirement",
    "requirement_metric",
    "source",
    "status",
    "subscription",
    "tag",
    "tagged_item",
    "task",
    "test",
    "test_configuration",
    "test_result",
    "test_run",
    "test_set",
    "test_set_metric",
    "test_test_set",
    "tool",
    "topic",
    "trace",
    "type_lookup",
]

_TENANT_POLICY_NEW = """
    CREATE POLICY tenant_isolation ON {table}
        USING (organization_id = (SELECT current_setting('app.current_organization')::uuid))
"""

_TENANT_POLICY_OLD = """
    CREATE POLICY tenant_isolation ON {table}
        USING (organization_id = current_setting('app.current_organization')::uuid)
"""

_PROJECT_POLICY_NEW = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = (SELECT NULLIF(current_setting('app.current_project', true), '')::uuid)
            OR project_id IS NULL
            OR (SELECT current_setting('app.current_organization', true)) = ''
        )
"""

_PROJECT_POLICY_OLD = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
            OR project_id IS NULL
            OR current_setting('app.current_organization', true) = ''
        )
"""

# auto_apply_rls_policies() from b8c9d0e1f2a3 with the policy bodies swapped for
# the subselect form. No event trigger is bound to it today, but keep it in step
# so a future trigger creates policies in the same shape.
_RLS_FUNCTION_TEMPLATE = """
CREATE OR REPLACE FUNCTION public.auto_apply_rls_policies()
RETURNS event_trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    tbl TEXT;
    exempt TEXT[] := ARRAY[
        'alembic_version', 'organization', 'token', 'user', 'refresh_token'
    ];
    project_exempt TEXT[] := ARRAY['project_membership'];
    reentry BOOLEAN;
BEGIN
    reentry := coalesce(
        nullif(current_setting('auto_rls.active', true), ''), 'false'
    )::boolean;
    IF reentry THEN
        RETURN;
    END IF;
    SET LOCAL auto_rls.active = 'true';

    FOR tbl IN
        SELECT DISTINCT c.relname
        FROM pg_event_trigger_ddl_commands() cmd
        JOIN pg_class c ON c.oid = cmd.objid
        WHERE cmd.schema_name = 'public'
          AND cmd.object_type IN ('table', 'table column')
          AND c.relkind = 'r'
    LOOP
        IF tbl = ANY(exempt) THEN
            CONTINUE;
        END IF;

        -- tenant_isolation for tables with organization_id
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = tbl
              AND column_name = 'organization_id'
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = tbl
              AND policyname = 'tenant_isolation'
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
            EXECUTE format(
                'ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', tbl);
            EXECUTE format(
                'CREATE POLICY tenant_isolation ON public.%I '
                'USING (organization_id = '
                '{tenant_expr})',
                tbl);
            RAISE NOTICE 'auto_apply_rls: tenant_isolation on %', tbl;
        END IF;

        -- project_isolation for tables with project_id (fail-closed, org-keyed
        -- passthrough). project_membership is exempt: it must stay org-scoped only.
        IF NOT (tbl = ANY(project_exempt)) AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = tbl
              AND column_name = 'project_id'
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = tbl
              AND policyname = 'project_isolation'
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
            EXECUTE format(
                'ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', tbl);
            EXECUTE format(
                'CREATE POLICY project_isolation ON public.%I '
                'AS RESTRICTIVE FOR ALL '
                'USING ('
                '    project_id = {project_expr}'
                '    OR project_id IS NULL'
                '    OR {org_passthrough_expr} = '''''
                ')',
                tbl);
            RAISE NOTICE 'auto_apply_rls: project_isolation on %', tbl;
        END IF;
    END LOOP;

    SET LOCAL auto_rls.active = 'false';
END;
$fn$;
"""

_RLS_FUNCTION_NEW = _RLS_FUNCTION_TEMPLATE.format(
    tenant_expr="(SELECT current_setting(''app.current_organization'')::uuid)",
    project_expr="(SELECT NULLIF(current_setting(''app.current_project'', true), '''')::uuid)",
    org_passthrough_expr="(SELECT current_setting(''app.current_organization'', true))",
)

_RLS_FUNCTION_OLD = _RLS_FUNCTION_TEMPLATE.format(
    tenant_expr="current_setting(''app.current_organization'')::uuid",
    project_expr="NULLIF(current_setting(''app.current_project'', true), '''')::uuid",
    org_passthrough_expr="current_setting(''app.current_organization'', true)",
)


def _swap_policies(tenant_body: str, project_body: str) -> None:
    for table in _TENANT_ISOLATION_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(tenant_body.format(table=table))
    for table in _PROJECT_ISOLATION_TABLES:
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(project_body.format(table=table))


def upgrade() -> None:
    _swap_policies(_TENANT_POLICY_NEW, _PROJECT_POLICY_NEW)
    op.execute(_RLS_FUNCTION_NEW)


def downgrade() -> None:
    _swap_policies(_TENANT_POLICY_OLD, _PROJECT_POLICY_OLD)
    op.execute(_RLS_FUNCTION_OLD)
