from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fcac5b8b5eb0"
down_revision: Union[str, None] = "34feae1682cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

"""
This migration implements row level security (RLS) for the application.
It ensures that each user can only access the data that belongs to their organization.

Note that this applies to all tables in the public schema, except alembic_version, 
organization and token.

alembic_version is not part of the application and is not subject to RLS.
organization is handled in a another migration, because we need to use the id of 
the organization to create the RLS policy.
token is not subject to RLS because it is used to authenticate the user in the 
first place: we can only know the organization of the user when we have 
authenticated them.
user is not subject to RLS because it is used to authenticate the user in the 
first place: we can only know the organization of the user when we have 
authenticated them.
"""


def upgrade() -> None:
    # Enable RLS on all tables in the public schema
    op.execute("""
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        -- Loop through all tables in the public schema
        FOR r IN
            -- Ordinary tables this role may alter: views and extension relations
            -- (e.g. pg_stat_statements, which RDS puts in public) can't take RLS,
            -- and on a fresh install every app table was created by this role.
            SELECT c.relname AS table_name FROM pg_class c
            WHERE c.relnamespace = 'public'::regnamespace
            AND c.relkind IN ('r', 'p')
            AND pg_has_role(current_user, c.relowner, 'MEMBER')
            AND NOT EXISTS (
                SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e'
            )
            AND c.relname NOT IN ('alembic_version', 'organization', 'token', 'user')
        LOOP
            -- Enable RLS for each table
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', r.table_name);
        END LOOP;
    END;
    $$;
    """)

    # Drop and recreate policies for organization isolation on all tables
    op.execute("""
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        -- Loop through all tables in the public schema, except alembic_version, 
        -- organization and token
        FOR r IN
            -- Ordinary tables this role may alter: views and extension relations
            -- (e.g. pg_stat_statements, which RDS puts in public) can't take RLS,
            -- and on a fresh install every app table was created by this role.
            SELECT c.relname AS table_name FROM pg_class c
            WHERE c.relnamespace = 'public'::regnamespace
            AND c.relkind IN ('r', 'p')
            AND pg_has_role(current_user, c.relowner, 'MEMBER')
            AND NOT EXISTS (
                SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e'
            )
            AND c.relname NOT IN ('alembic_version', 'organization', 'token', 'user')
        LOOP
            -- Drop the existing organization isolation policy if it exists
            BEGIN
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON public.%I;', 
                               r.table_name);
            EXCEPTION WHEN OTHERS THEN
                -- Ignore errors if the policy doesn't exist
                NULL;
            END;

            -- Create the organization isolation policy for each table
            EXECUTE format('
                CREATE POLICY tenant_isolation ON public.%I
                USING (organization_id = current_setting(''app.current_organization'')::uuid);
            ', r.table_name);
        END LOOP;
    END;
    $$;
    """)


def downgrade() -> None:
    # Drop policies on downgrade
    op.execute("""
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        -- Loop through all tables in the public schema, except alembic_version, 
        -- organization and token
        FOR r IN
            -- Ordinary tables this role may alter: views and extension relations
            -- (e.g. pg_stat_statements, which RDS puts in public) can't take RLS,
            -- and on a fresh install every app table was created by this role.
            SELECT c.relname AS table_name FROM pg_class c
            WHERE c.relnamespace = 'public'::regnamespace
            AND c.relkind IN ('r', 'p')
            AND pg_has_role(current_user, c.relowner, 'MEMBER')
            AND NOT EXISTS (
                SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e'
            )
            AND c.relname NOT IN ('alembic_version', 'organization', 'token', 'user')
        LOOP
            -- Drop the organization isolation policy for each table
            BEGIN
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON public.%I;', 
                               r.table_name);
            EXCEPTION WHEN OTHERS THEN
                -- Ignore errors if the policy doesn't exist
                NULL;
            END;
        END LOOP;
    END;
    $$;
    """)

    # Disable RLS for all tables on downgrade
    op.execute("""
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        -- Loop through all tables in the public schema
        FOR r IN
            -- Ordinary tables this role may alter: views and extension relations
            -- (e.g. pg_stat_statements, which RDS puts in public) can't take RLS,
            -- and on a fresh install every app table was created by this role.
            SELECT c.relname AS table_name FROM pg_class c
            WHERE c.relnamespace = 'public'::regnamespace
            AND c.relkind IN ('r', 'p')
            AND pg_has_role(current_user, c.relowner, 'MEMBER')
            AND NOT EXISTS (
                SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e'
            )
            AND c.relname NOT IN ('alembic_version', 'organization', 'token', 'user')
        LOOP
            -- Disable RLS for each table
            EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY;', r.table_name);
        END LOOP;
    END;
    $$;
    """)
