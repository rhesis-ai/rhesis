"""Harden all tenant_isolation RLS policies against missing/empty GUC

The original RLS migration (fcac5b8b5eb0) and the backfill migration
(d4e5f6a7b8c3) created tenant_isolation policies using:

    organization_id = current_setting('app.current_organization')::uuid

This crashes in two ways when no tenant GUC is set (SSO callback,
migrations, seeding):

1. ``unrecognized configuration parameter`` -- current_setting without
   missing_ok raises when the GUC has never been SET in the session.
2. ``invalid input syntax for type uuid: ""`` -- even with missing_ok,
   an empty string cannot be cast to uuid.

Three tables were already fixed individually:
- organization_member (c5d6e7f8a9b0)
- role, role_permission (a0b1c2d3e4f5) -- custom join-based policies

This migration applies the standard trusted-context pattern to every
remaining table whose tenant_isolation policy still uses the bare cast.
It uses a dynamic PL/pgSQL block to find and rewrite all affected
policies in one pass.

Revision ID: d5e6f7a8b9c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d5e6f7a8b9c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SKIP_TABLES = (
    "organization",
    "organization_member",
    "role",
    "role_permission",
)


def upgrade() -> None:
    skip = ", ".join(f"'{t}'" for t in _SKIP_TABLES)
    op.execute(
        f"""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN
                SELECT DISTINCT pol.tablename
                FROM pg_policies pol
                JOIN information_schema.columns col
                  ON col.table_schema = pol.schemaname
                 AND col.table_name  = pol.tablename
                 AND col.column_name = 'organization_id'
                WHERE pol.schemaname = 'public'
                  AND pol.policyname = 'tenant_isolation'
                  AND pol.tablename NOT IN ({skip})
            LOOP
                EXECUTE format(
                    'DROP POLICY IF EXISTS tenant_isolation ON public.%I', r.tablename
                );
                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON public.%I
                        USING (
                            NULLIF(current_setting(''app.current_organization'', true), '''') IS NULL
                            OR organization_id = NULLIF(
                                current_setting(''app.current_organization'', true), ''''
                            )::uuid
                        )
                        WITH CHECK (
                            NULLIF(current_setting(''app.current_organization'', true), '''') IS NULL
                            OR organization_id = NULLIF(
                                current_setting(''app.current_organization'', true), ''''
                            )::uuid
                        )',
                    r.tablename
                );
            END LOOP;
        END;
        $$;
        """
    )


def downgrade() -> None:
    skip = ", ".join(f"'{t}'" for t in _SKIP_TABLES)
    op.execute(
        f"""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN
                SELECT DISTINCT pol.tablename
                FROM pg_policies pol
                JOIN information_schema.columns col
                  ON col.table_schema = pol.schemaname
                 AND col.table_name  = pol.tablename
                 AND col.column_name = 'organization_id'
                WHERE pol.schemaname = 'public'
                  AND pol.policyname = 'tenant_isolation'
                  AND pol.tablename NOT IN ({skip})
            LOOP
                EXECUTE format(
                    'DROP POLICY IF EXISTS tenant_isolation ON public.%I', r.tablename
                );
                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON public.%I
                        USING (
                            organization_id = current_setting(''app.current_organization'')::uuid
                        )',
                    r.tablename
                );
            END LOOP;
        END;
        $$;
        """
    )
