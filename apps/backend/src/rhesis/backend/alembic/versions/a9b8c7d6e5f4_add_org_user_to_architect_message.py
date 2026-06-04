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


# Tables whose RLS must be quiet while this migration runs:
#   - architect_message: FK validation + the policy the add_column trigger creates
#   - architect_session: the step-3 backfill reads it
#   - organization, user:  FK validation reads them as the FK targets
# Their tenant_isolation policies call current_setting('app.current_organization')
# WITHOUT missing_ok=true, so any policy evaluation without that GUC set raises
# "unrecognized configuration parameter".
_RLS_TABLES = ["architect_message", "architect_session", "organization", '"user"']


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Disable RLS on every table this migration touches, for the migration's
    #    duration. The remote DB has FORCE ROW LEVEL SECURITY on these tables, and
    #    op.add_column fails because PostgreSQL validates the new FK with a bulk
    #    SELECT over the child + FK-target tables whose tenant_isolation policies
    #    call current_setting('app.current_organization') without missing_ok=true,
    #    which the migration session never set.
    #
    #    We disable unconditionally rather than gating on the migration role's
    #    BYPASSRLS attribute: PostgreSQL's FK initial-validation query
    #    (RI_Initial_Check) runs under the *table owner's* identity, not the
    #    connected current_user, so current_user's BYPASSRLS is the wrong signal —
    #    on Cloud SQL the login role reports BYPASSRLS while the table owner does
    #    not, and the validation still hit the policy. DISABLE ROW LEVEL SECURITY
    #    is table-level and role-independent, so it sidesteps the owner switch
    #    entirely.
    #
    #    This is safe and leaves no observable RLS gap: Alembic runs the whole
    #    upgrade in ONE transaction with transactional DDL, and DISABLE/ENABLE takes
    #    an ACCESS EXCLUSIVE lock, so no other session can read these tables while
    #    RLS is off and the disable→enable is only ever observed atomically (already
    #    re-enabled) at commit. On stg/prd (rhesis-admin owns the tables and
    #    bypasses RLS) the round-trip is a harmless no-op. The round-trip does not
    #    affect the FORCE flag.
    for table in _RLS_TABLES:
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    # 2. Add organization_id and user_id columns (nullable; values come from the
    #    parent session). Adding organization_id fires the auto_apply_rls event
    #    trigger which creates tenant_isolation automatically, but we (re)create it
    #    explicitly in step 4 so this migration is deterministic regardless of
    #    trigger state.
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

    # 3. Backfill organization_id / user_id from the parent session (mirrors the
    #    project_membership backfill in e5f6a7b8c9d0).
    conn.execute(
        sa.text(
            """
            UPDATE architect_message m
            SET organization_id = s.organization_id,
                user_id = s.user_id
            FROM architect_session s
            WHERE m.session_id = s.id
              AND (m.organization_id IS NULL OR m.user_id IS NULL)
            """
        )
    )
    for table in _RLS_TABLES:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

    # 4. Ensure the permissive tenant_isolation policy exists (the missing piece).
    op.execute("ALTER TABLE architect_message FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON architect_message")
    op.execute(_TENANT_POLICY)


def downgrade() -> None:
    # Drop indexes first (DROP INDEX does not fire the auto_apply_rls event
    # trigger, so order is free here).
    op.drop_index("ix_architect_message_user_id", table_name="architect_message")
    op.drop_index("ix_architect_message_organization_id", table_name="architect_message")

    # Drop the policy, then drop organization_id BEFORE user_id. Each DROP COLUMN
    # is an ALTER TABLE that re-fires auto_apply_rls_policies; if organization_id
    # were still present when we dropped user_id, the trigger would recreate
    # tenant_isolation and the subsequent DROP COLUMN organization_id would fail
    # on the policy dependency. Removing organization_id first means the trigger
    # never sees an org column without a policy.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON architect_message")
    op.drop_column("architect_message", "organization_id")
    op.drop_column("architect_message", "user_id")
