"""Bring job, activity_log, annotation and test_set RLS policies to the canonical bodies

``job``, ``activity_log`` (d2c3b4a5e6f7) and ``annotation`` (facfa552f715) created
``project_isolation`` with ``OR current_setting('app.current_project', true) = ''``,
so a session with an org but no project saw every project's rows in that org. The
canonical body (b8d2f3e4a5c6) only passes everything when the *org* GUC is blank.
Their ``tenant_isolation`` moves to the subselect form too.

``test_set.tenant_isolation`` (4f8d34f13c9c) kept a ``visibility = 'public'`` branch
that passed rows from every org, and cast the GUCs without NULLIF. The CHECK
constraint on ``visibility`` made the branch unreachable; it is dropped here. The
owner-only rule for ``visibility = 'user'`` stays, now inside the org.

Revision ID: e7b2c9d41f08
Revises: c47fd570587b
Create Date: 2026-11-11
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e7b2c9d41f08"
down_revision: Union[str, None] = "c47fd570587b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("job", "activity_log", "annotation")

_ORG = "(SELECT NULLIF(current_setting('app.current_organization', true), '')::uuid)"
_USER = "(SELECT NULLIF(current_setting('app.current_user', true), '')::uuid)"

_TENANT = f"""
    CREATE POLICY tenant_isolation ON {{table}}
        USING (organization_id = {_ORG})
"""

_PROJECT = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = (SELECT NULLIF(current_setting('app.current_project', true), '')::uuid)
            OR project_id IS NULL
            OR (SELECT current_setting('app.current_organization', true)) = ''
        )
"""

_TEST_SET_TENANT = f"""
    CREATE POLICY tenant_isolation ON test_set
        AS PERMISSIVE
        FOR ALL
        USING (
            organization_id = {_ORG}
            AND (
                visibility = 'organization'
                OR (visibility = 'user' AND user_id = {_USER})
            )
        )
        WITH CHECK (organization_id = {_ORG})
"""

# Previous bodies, for downgrade.
_OLD_TENANT_JOB = """
    CREATE POLICY tenant_isolation ON {table}
        USING (
            organization_id = NULLIF(current_setting('app.current_organization', true), '')::uuid
        )
"""

_OLD_PROJECT = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
            OR project_id IS NULL
            OR current_setting('app.current_project', true) = ''
        )
"""

_OLD_TEST_SET_TENANT = """
    CREATE POLICY tenant_isolation ON test_set
        AS PERMISSIVE
        FOR ALL
        TO public
        USING (
            CASE
                WHEN visibility = 'public' THEN TRUE
                WHEN visibility = 'organization' THEN organization_id =
                    CURRENT_SETTING('app.current_organization', TRUE)::uuid
                WHEN visibility = 'user' THEN user_id =
                    CURRENT_SETTING('app.current_user', TRUE)::uuid
                ELSE FALSE
            END
        )
        WITH CHECK (organization_id = CURRENT_SETTING('app.current_organization', TRUE)::uuid)
"""


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_PROJECT.format(table=table))
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(_TENANT.format(table=table))

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON test_set")
    op.execute(_TEST_SET_TENANT)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON test_set")
    op.execute(_OLD_TEST_SET_TENANT)

    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_OLD_PROJECT.format(table=table))
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        # annotation already had the subselect form; it keeps it.
        body = _TENANT if table == "annotation" else _OLD_TENANT_JOB
        op.execute(body.format(table=table))
