"""Add audit_destination, where an org streams its audit log

Maps to ``AuditDestination`` in ``ee/backend/.../ee/audit/streaming/models.py``.
Org-scoped, no ``project_id``, so ``tenant_isolation`` only.

Revision ID: a7c3e9d2f410
Revises: eb74b077a892
Create Date: 2026-10-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7c3e9d2f410"
down_revision: Union[str, None] = "eb74b077a892"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "audit_destination"
# Keeps a hand-installed auto_rls_on_ddl event trigger from adding its own policies.
_SKIP_AUTO_RLS = "SET LOCAL auto_rls.active = 'true'"
# The body from f4a91c3e7b52.
_TENANT_POLICY = f"""
CREATE POLICY tenant_isolation ON {_TABLE} AS PERMISSIVE FOR ALL TO public
USING (organization_id = (SELECT NULLIF(current_setting('app.current_organization', true), '')::uuid))
"""


def upgrade() -> None:
    op.execute(_SKIP_AUTO_RLS)
    timestamp = sa.DateTime(timezone=True)
    op.create_table(
        _TABLE,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nano_id", sa.String(), nullable=True, unique=True),
        sa.Column("created_at", timestamp, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", timestamp, server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", timestamp, nullable=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("paused_reason", sa.String(16), nullable=True),
        sa.Column("cursor_recorded_at", timestamp, nullable=False),
        sa.Column("cursor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", timestamp, nullable=True),
        sa.Column("last_success_at", timestamp, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", timestamp, nullable=True),
    )
    op.create_index(f"ix_{_TABLE}_organization_id", _TABLE, ["organization_id"])
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_TABLE}")
    op.execute(_TENANT_POLICY)


def downgrade() -> None:
    op.execute(_SKIP_AUTO_RLS)
    op.drop_table(_TABLE)
