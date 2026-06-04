"""Add organization_id and user_id to architect_message (+ tenant RLS)

architect_message originally had only a project_id column (no organization_id),
so the RLS migrations gave it the RESTRICTIVE project_isolation policy but never a
PERMISSIVE tenant_isolation policy. In PostgreSQL a table with RLS + FORCE ROW
LEVEL SECURITY and ONLY restrictive policies denies every INSERT/SELECT for
non-superuser roles: restrictive policies can narrow access but cannot grant it,
so at least one permissive policy must permit the row. The result was a
"new row violates row-level security policy for table architect_message" error
on every insert under the runtime (app) DB role, while local single-role setups
that bypass RLS worked fine.

Fix: give architect_message organization_id and user_id columns (inherited from
the parent architect_session), backfill them, and add the permissive
tenant_isolation policy. Adding the organization_id column also lets the ORM
auto-stamp / _auto_populate_tenant_fields helpers fill it on every new row.

Revision ID: a9b8c7d6e5f4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON architect_message
        USING (organization_id = current_setting('app.current_organization')::uuid)
"""


def upgrade() -> None:
    # The migration role bypasses RLS (prod: rhesis-admin has BYPASSRLS; dev:
    # nocodb-user was granted BYPASSRLS), so RLS policies are never evaluated for
    # this connection — FK validation, the backfill, and the auto_rls_on_ddl
    # trigger's policy creation all run cleanly without any RLS handling here.

    # 1. Add organization_id and user_id (nullable; values come from the parent
    #    session). Adding organization_id fires the auto_rls_on_ddl trigger
    #    (d4e5f6a7b8c3), which enables RLS and creates tenant_isolation
    #    automatically; we still (re)create it explicitly in step 3 so the
    #    migration is deterministic regardless of trigger state.
    op.add_column(
        "architect_message",
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "architect_message",
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_architect_message_organization_id",
        "architect_message",
        ["organization_id"],
    )
    op.create_index(
        "ix_architect_message_user_id",
        "architect_message",
        ["user_id"],
    )

    # 2. Backfill organization_id / user_id from the parent session (mirrors the
    #    project_membership backfill in e5f6a7b8c9d0).
    op.execute(
        """
        UPDATE architect_message m
        SET organization_id = s.organization_id,
            user_id = s.user_id
        FROM architect_session s
        WHERE m.session_id = s.id
          AND (m.organization_id IS NULL OR m.user_id IS NULL)
        """
    )

    # 3. Ensure the permissive tenant_isolation policy exists (the missing piece).
    op.execute("ALTER TABLE architect_message FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON architect_message")
    op.execute(_TENANT_POLICY)


def downgrade() -> None:
    op.drop_index("ix_architect_message_user_id", table_name="architect_message")
    op.drop_index("ix_architect_message_organization_id", table_name="architect_message")

    # Drop the policy, then drop organization_id BEFORE user_id. Each DROP COLUMN
    # re-fires auto_apply_rls_policies; removing organization_id first means the
    # trigger never sees an org column without a policy and so cannot recreate
    # tenant_isolation (which would block the subsequent DROP COLUMN).
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON architect_message")
    op.drop_column("architect_message", "organization_id")
    op.drop_column("architect_message", "user_id")
