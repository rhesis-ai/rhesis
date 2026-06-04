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

# FK constraint names (explicit so the NOT VALID variant and downgrade can
# reference them).
_ORG_FK = "architect_message_organization_id_fkey"
_USER_FK = "architect_message_user_id_fkey"

# Low-traffic tables whose RLS we toggle during the backfill. We deliberately do
# NOT include the FK targets (organization, user): DISABLE ROW LEVEL SECURITY
# takes an ACCESS EXCLUSIVE lock, and on those hot tables it serializes behind
# every live read and hung the migrate job to its 600s timeout. The FKs are added
# NOT VALID below so they never trigger the RLS-sensitive initial validation scan
# against organization/user, removing the need to touch their RLS at all.
_RLS_TABLES = ("architect_message", "architect_session")


def upgrade() -> None:
    # This migration must run correctly whether or not the Alembic role bypasses
    # RLS. We don't rely on BYPASSRLS (prod's rhesis-admin has it, but dev/local
    # bootstrap and the migrate.sh APP_DB_USER fallback may not), and FK initial
    # validation runs under the *table owner* identity anyway — so current_user's
    # BYPASSRLS is not a reliable signal. Instead we defend explicitly.
    conn = op.get_bind()

    # Fail fast instead of hanging behind a long-held lock.
    conn.execute(sa.text("SET LOCAL lock_timeout = '120s'"))

    # Neutralize the auto_rls_on_ddl event trigger (d4e5f6a7b8c3) for this
    # transaction so our DDL can't re-enable RLS / recreate policies mid-migration.
    # The trigger uses this same GUC as its own reentry guard.
    conn.execute(sa.text("SET LOCAL auto_rls.active = 'true'"))

    # Capture prior RLS state, then disable RLS on the low-traffic architect_*
    # tables for the duration of the backfill (so the UPDATE isn't filtered by
    # tenant policies under a non-bypass role). DISABLE only flips relrowsecurity;
    # the FORCE flag (relforcerowsecurity) is preserved.
    prior_rls: dict[str, bool] = {}
    for tbl in _RLS_TABLES:
        enabled = conn.execute(
            sa.text("SELECT relrowsecurity FROM pg_class WHERE relname = :t"),
            {"t": tbl},
        ).scalar()
        prior_rls[tbl] = bool(enabled)
        conn.execute(sa.text(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY"))

    # 1. Add nullable columns (no inline FK, so no immediate validation scan).
    op.add_column(
        "architect_message",
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "architect_message",
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # Add the FKs NOT VALID: PostgreSQL skips the initial validation scan, so FK
    # creation never reads organization/user under RLS and never needs their RLS
    # disabled. New/modified rows are still checked. Existing rows are safe to
    # leave unvalidated because the columns are brand new (all NULL) and the
    # backfill below populates them consistently from the parent session.
    op.create_foreign_key(
        _ORG_FK,
        "architect_message",
        "organization",
        ["organization_id"],
        ["id"],
        postgresql_not_valid=True,
    )
    op.create_foreign_key(
        _USER_FK,
        "architect_message",
        "user",
        ["user_id"],
        ["id"],
        postgresql_not_valid=True,
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

    # 3. Ensure the permissive tenant_isolation policy exists (the missing piece),
    #    then restore RLS on the architect_* tables we toggled.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON architect_message")
    op.execute(_TENANT_POLICY)

    op.execute("ALTER TABLE architect_message FORCE ROW LEVEL SECURITY")
    for tbl in _RLS_TABLES:
        if prior_rls[tbl]:
            conn.execute(sa.text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    conn = op.get_bind()
    # Neutralize the trigger so DROP COLUMN can't re-fire policy creation.
    conn.execute(sa.text("SET LOCAL auto_rls.active = 'true'"))

    op.drop_index("ix_architect_message_user_id", table_name="architect_message")
    op.drop_index("ix_architect_message_organization_id", table_name="architect_message")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON architect_message")
    op.drop_constraint(_USER_FK, "architect_message", type_="foreignkey")
    op.drop_constraint(_ORG_FK, "architect_message", type_="foreignkey")
    op.drop_column("architect_message", "organization_id")
    op.drop_column("architect_message", "user_id")
