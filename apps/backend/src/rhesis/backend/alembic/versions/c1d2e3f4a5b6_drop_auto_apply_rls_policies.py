"""Drop the unused auto_apply_rls_policies() function

d4e5f6a7b8c3 was meant to bind this function to an ``auto_rls_on_ddl`` event
trigger so new tenant tables got RLS policies automatically. ``CREATE EVENT
TRIGGER`` needs superuser, which the migration role does not have on CNPG, so
the trigger was removed (#1941) and never installed. The function stayed and
was kept in step by b8c9d0e1f2a3 and b8d2f3e4a5c6, but nothing calls it.

New tenant tables create their policies in their own migration instead, and
``tests/backend/security/test_rls_coverage.py`` fails CI when one is missing.
That catches the mistake before merge, works on every Postgres the app runs on,
and keeps migrations free of DDL side effects.

If someone did install the trigger by hand, the function is left in place with
a notice: only a superuser can drop the trigger, and failing here would block
the deploy.

Revision ID: c1d2e3f4a5b6
Revises: f4a91c3e7b52
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "f4a91c3e7b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DROP_UNLESS_BOUND = """
DO $$
DECLARE
    fn regprocedure := to_regprocedure('public.auto_apply_rls_policies()');
BEGIN
    IF fn IS NULL THEN
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_event_trigger WHERE evtfoid = fn) THEN
        RAISE NOTICE 'auto_apply_rls_policies() is bound to an event trigger; '
                     'a superuser must DROP EVENT TRIGGER auto_rls_on_ddl first';
        RETURN;
    END IF;
    DROP FUNCTION public.auto_apply_rls_policies();
END
$$;
"""

# Verbatim snapshot of the definition b8d2f3e4a5c6 left in place.
_RLS_FUNCTION = """
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
                '(SELECT current_setting(''app.current_organization'')::uuid))',
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
                '    project_id = (SELECT NULLIF(current_setting(''app.current_project'', true), '''')::uuid)'
                '    OR project_id IS NULL'
                '    OR (SELECT current_setting(''app.current_organization'', true)) = '''''
                ')',
                tbl);
            RAISE NOTICE 'auto_apply_rls: project_isolation on %', tbl;
        END IF;
    END LOOP;

    SET LOCAL auto_rls.active = 'false';
END;
$fn$;
"""


def upgrade() -> None:
    op.execute(_DROP_UNLESS_BOUND)


def downgrade() -> None:
    op.execute(_RLS_FUNCTION)
