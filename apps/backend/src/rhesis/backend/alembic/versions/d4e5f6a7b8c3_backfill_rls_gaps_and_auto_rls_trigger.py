"""Backfill missing RLS policies and add auto-RLS event trigger

Addresses two issues:

1. **Backfill gaps** — Several tables added after the original RLS migration
   (fcac5b8b5eb0) never received a tenant_isolation policy. The Phase 5
   project_isolation migration (c3d4e5f6a7b2) covered the 36 tables with
   ProjectMixin but missed endpoint, experiment, trace, and project_membership
   which had pre-existing project_id columns.

2. **Auto-RLS event trigger** — A PostgreSQL event trigger that automatically
   applies tenant_isolation and/or project_isolation policies whenever a
   CREATE TABLE or ALTER TABLE adds organization_id or project_id columns.
   This prevents future tables from silently lacking RLS coverage.

Exempt tables (deliberately excluded from automatic policies):
  - token: queried before tenant context is bound
  - user: identity table, cross-org lookups required
  - organization: has its own RLS policy
  - alembic_version: schema management
  - refresh_token: auth infrastructure, no tenant columns

Revision ID: d4e5f6a7b8c3
Revises: c3d4e5f6a7b2
Create Date: 2026-06-01

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c3"
down_revision: Union[str, None] = "c3d4e5f6a7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that need tenant_isolation added (have organization_id, no policy).
# RLS is already enabled on most via Phase 5; auth_client, project_membership,
# and trace also need ENABLE + FORCE.
_NEED_TENANT_ISOLATION = [
    "architect_session",
    "auth_client",
    "behavior_metric",
    "chunk",
    "comment",
    "embedding",
    "file",
    "metric",
    "model",
    "project_membership",
    "task",
    "test_set_metric",
    "tool",
    "trace",
]

# Tables that need project_isolation added (have project_id, no policy).
# endpoint and experiment had pre-existing project_id columns that Phase 5
# did not cover. project_membership and trace need both policies.
_NEED_PROJECT_ISOLATION = [
    "endpoint",
    "experiment",
    "project_membership",
    "trace",
]

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON {table}
        USING (organization_id = current_setting('app.current_organization')::uuid)
"""

_PROJECT_POLICY = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
            OR project_id IS NULL
            OR current_setting('app.current_project', true) = ''
        )
"""

_EVENT_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION public.auto_apply_rls_policies()
RETURNS event_trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    tbl TEXT;
    exempt TEXT[] := ARRAY[
        'alembic_version', 'organization', 'token', 'user', 'refresh_token'
    ];
    reentry BOOLEAN;
BEGIN
    -- Guard against infinite recursion: ALTER TABLE ENABLE ROW LEVEL SECURITY
    -- itself fires ddl_command_end, re-entering this function. Use a
    -- transaction-local GUC as a reentry guard.
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
                'current_setting(''app.current_organization'')::uuid)',
                tbl);
            RAISE NOTICE 'auto_apply_rls: tenant_isolation on %', tbl;
        END IF;

        -- project_isolation for tables with project_id
        IF EXISTS (
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
                '    project_id = NULLIF('
                'current_setting(''app.current_project'', true), '''')::uuid'
                '    OR project_id IS NULL'
                '    OR current_setting(''app.current_project'', true) = '''''
                ')',
                tbl);
            RAISE NOTICE 'auto_apply_rls: project_isolation on %', tbl;
        END IF;
    END LOOP;

    -- Reset so subsequent DDL in the same transaction is still handled.
    -- The guard only needs to block reentry from our own ALTER TABLE calls
    -- above, not from independent DDL statements that follow.
    SET LOCAL auto_rls.active = 'false';
END;
$fn$;
"""

_EVENT_TRIGGER = """
CREATE EVENT TRIGGER auto_rls_on_ddl
    ON ddl_command_end
    WHEN TAG IN ('CREATE TABLE', 'ALTER TABLE')
    EXECUTE FUNCTION public.auto_apply_rls_policies();
"""


def upgrade() -> None:
    # 1. Backfill tenant_isolation on tables that were added after the
    #    original RLS migration and never received the policy.
    for table in _NEED_TENANT_ISOLATION:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(_TENANT_POLICY.format(table=table))

    # 2. Backfill project_isolation on tables with pre-existing project_id
    #    that Phase 5 did not cover.
    for table in _NEED_PROJECT_ISOLATION:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_PROJECT_POLICY.format(table=table))

    # 3. Install the event trigger so future tables get policies automatically.
    #    CREATE OR REPLACE handles re-runs for the function. DROP IF EXISTS makes
    #    the event trigger itself idempotent too.
    op.execute(_EVENT_TRIGGER_FUNCTION)
    op.execute("DROP EVENT TRIGGER IF EXISTS auto_rls_on_ddl")
    op.execute(_EVENT_TRIGGER)


def downgrade() -> None:
    # Drop event trigger and function
    op.execute("DROP EVENT TRIGGER IF EXISTS auto_rls_on_ddl")
    op.execute("DROP FUNCTION IF EXISTS public.auto_apply_rls_policies()")

    # Drop backfilled project_isolation policies
    for table in reversed(_NEED_PROJECT_ISOLATION):
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")

    # Drop backfilled tenant_isolation policies
    for table in reversed(_NEED_TENANT_ISOLATION):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        # Don't disable RLS — other policies may still be active
