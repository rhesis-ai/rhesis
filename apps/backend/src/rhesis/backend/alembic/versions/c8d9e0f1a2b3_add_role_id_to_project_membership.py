"""Add nullable role_id column to project_membership (SP6 seam for EE roles)

The community tier keeps binary membership semantics (member vs. not). This
column is the seam that Phase 2 (EE, SP8) fills with real role rows from the
``role`` table once that table exists.  While ``role_id`` is NULL the existing
DefaultAuthorizationProvider ignores it; the EE PermissionAuthorizationProvider
(SP8) reads it to resolve the caller's effective project role.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table, column):
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).fetchone()
        is not None
    )


def _index_exists(conn, index_name):
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": index_name},
        ).fetchone()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, "project_membership", "role_id"):
        op.add_column(
            "project_membership",
            sa.Column(
                "role_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
    if not _index_exists(conn, "ix_project_membership_role_id"):
        op.create_index(
            "ix_project_membership_role_id",
            "project_membership",
            ["role_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_project_membership_role_id", table_name="project_membership")
    op.drop_column("project_membership", "role_id")
