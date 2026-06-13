"""Fail-closed project_isolation RLS (passthrough keyed on empty org)

Closes a cross-project access hole. The original project_isolation policies
(c3d4e5f6a7b2, d4e5f6a7b8c3) had an "OR current_setting('app.current_project') = ''"
passthrough: any session without an active project saw EVERY project's rows. A
user request that omitted the project context (e.g. SSR detail pages that did not
forward X-Project-Id) therefore leaked entities from other projects.

This migration makes project isolation fail-closed by re-keying the passthrough on
an empty ORGANIZATION instead of an empty project:

    project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
    OR project_id IS NULL
    OR current_setting('app.current_organization', true) = ''

Semantics:
  - org set + project set   -> rows in that project plus org-level (NULL) rows
  - org set + project unset -> org-level (NULL) rows only          (FAIL-CLOSED)
  - org unset               -> passthrough (system/bootstrap sessions that run
                               before any tenant scope is bound, e.g. the Celery
                               failure-signal handler scanning by task id)

Authenticated user requests always carry an org, so "no active project" now means
"org-level rows only" rather than "everything". Migrations run as an admin role and
bypass RLS regardless.

project_membership change: its project_isolation policy is DROPPED entirely. It is
the access-control join table that must be queryable by org scope alone (before a
project is resolved and across all of a user's projects); under a fail-closed
project policy it would become invisible whenever the active project did not match.
It keeps tenant_isolation (org) only. The auto-RLS trigger is updated to never
re-add project_isolation to it.

Revision ID: b8c9d0e1f2a3
Revises: f6a7b8c9d0e1
Create Date: 2026-06-03

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every table that carries a project_isolation policy today, EXCEPT
# project_membership (handled separately — its policy is dropped, not recreated).
_PROJECT_ISOLATION_TABLES = [
    # From c3d4e5f6a7b2 (_ALL_SCOPED_TABLES)
    "test_set",
    "test",
    "test_result",
    "test_run",
    "test_configuration",
    "test_context",
    "behavior",
    "category",
    "demographic",
    "dimension",
    "use_case",
    "risk",
    "topic",
    "metric",
    "prompt",
    "prompt_template",
    "response_pattern",
    "model",
    "source",
    "chunk",
    "file",
    "tool",
    "tag",
    "tagged_item",
    "status",
    "type_lookup",
    "task",
    "comment",
    "architect_session",
    "embedding",
    "subscription",
    "test_set_metric",
    "test_test_set",
    "behavior_metric",
    "prompt_test_set",
    "architect_message",
    # From d4e5f6a7b8c3 (_NEED_PROJECT_ISOLATION, minus project_membership)
    "endpoint",
    "experiment",
    "trace",
]

# New fail-closed policy body. Passthrough keyed on empty ORG (system context),
# NOT empty project.
_FAIL_CLOSED_PROJECT_POLICY = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
            OR project_id IS NULL
            OR current_setting('app.current_organization', true) = ''
        )
"""

# Old (leaky) policy body, used to restore on downgrade. Passthrough keyed on
# empty project.
_LEAKY_PROJECT_POLICY = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
            OR project_id IS NULL
            OR current_setting('app.current_project', true) = ''
        )
"""


# --- Event-trigger function: fail-closed variant -----------------------------
# Mirrors d4e5f6a7b8c3's auto_apply_rls_policies but (a) uses the org-keyed
# passthrough for new project_isolation policies and (b) never adds
# project_isolation to project_membership.
_EVENT_TRIGGER_FUNCTION_NEW = """
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
                'current_setting(''app.current_organization'')::uuid)',
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
                '    project_id = NULLIF('
                'current_setting(''app.current_project'', true), '''')::uuid'
                '    OR project_id IS NULL'
                '    OR current_setting(''app.current_organization'', true) = '''''
                ')',
                tbl);
            RAISE NOTICE 'auto_apply_rls: project_isolation on %', tbl;
        END IF;
    END LOOP;

    SET LOCAL auto_rls.active = 'false';
END;
$fn$;
"""

# Old function body (project-keyed passthrough, no project_exempt list) for
# downgrade.
_EVENT_TRIGGER_FUNCTION_OLD = """
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

    SET LOCAL auto_rls.active = 'false';
END;
$fn$;
"""


def upgrade() -> None:
    # 1. Recreate project_isolation with the fail-closed (org-keyed) body.
    for table in _PROJECT_ISOLATION_TABLES:
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_FAIL_CLOSED_PROJECT_POLICY.format(table=table))

    # 2. project_membership: drop project_isolation entirely. It stays org-scoped
    #    only (tenant_isolation remains).
    op.execute("DROP POLICY IF EXISTS project_isolation ON project_membership")

    # 3. Recreate the auto-RLS trigger function with the fail-closed body and the
    #    project_membership exemption. CREATE OR REPLACE keeps the existing event
    #    trigger bound to the same function name.
    op.execute(_EVENT_TRIGGER_FUNCTION_NEW)


def downgrade() -> None:
    # Restore the leaky (project-keyed) function body first. NOTE: we must NOT run
    # ALTER TABLE ... ENABLE/FORCE ROW LEVEL SECURITY below -- RLS is already enabled
    # on every table here (it was never disabled), and an ALTER TABLE would fire the
    # auto_rls_on_ddl event trigger, which would auto-create project_isolation and
    # collide with the explicit CREATE POLICY. CREATE/DROP POLICY do not fire the
    # trigger (tag not in its WHEN clause), so the policy swaps below are safe.
    op.execute(_EVENT_TRIGGER_FUNCTION_OLD)

    # Restore the leaky project_isolation policy on project_membership.
    op.execute("DROP POLICY IF EXISTS project_isolation ON project_membership")
    op.execute(_LEAKY_PROJECT_POLICY.format(table="project_membership"))

    # Restore the leaky policy body on all other tables.
    for table in reversed(_PROJECT_ISOLATION_TABLES):
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_LEAKY_PROJECT_POLICY.format(table=table))
