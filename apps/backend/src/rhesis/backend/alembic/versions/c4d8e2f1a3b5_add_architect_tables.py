"""add architect session and message tables

Revision ID: c4d8e2f1a3b5
Revises: 97b38ee1a6e1
Create Date: 2026-03-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

import rhesis.backend

# revision identifiers, used by Alembic.
revision: str = "c4d8e2f1a3b5"
down_revision: Union[str, None] = "97b38ee1a6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _index_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    for table in ("architect_session", "architect_message"):
        if table not in insp.get_table_names():
            continue
        for idx in insp.get_indexes(table):
            if idx["name"] == name:
                return True
    return False


def upgrade() -> None:
    if not _table_exists("architect_session"):
        op.create_table(
            "architect_session",
            sa.Column(
                "id",
                rhesis.backend.app.models.guid.GUID(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("nano_id", sa.String(12), unique=True, nullable=False),
            sa.Column(
                "organization_id",
                rhesis.backend.app.models.guid.GUID(),
                sa.ForeignKey("organization.id"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                rhesis.backend.app.models.guid.GUID(),
                sa.ForeignKey("user.id"),
                nullable=False,
            ),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("mode", sa.String(50), nullable=False, server_default="discovery"),
            sa.Column("plan_data", postgresql.JSONB(), nullable=True),
            sa.Column("agent_state", postgresql.JSONB(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("architect_message"):
        op.create_table(
            "architect_message",
            sa.Column(
                "id",
                rhesis.backend.app.models.guid.GUID(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("nano_id", sa.String(12), unique=True, nullable=False),
            sa.Column(
                "session_id",
                rhesis.backend.app.models.guid.GUID(),
                sa.ForeignKey("architect_session.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(), nullable=True),
            sa.Column("attachments", postgresql.JSONB(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("ix_architect_session_user_id"):
        op.create_index(
            "ix_architect_session_user_id",
            "architect_session",
            ["user_id"],
        )
    if not _index_exists("ix_architect_session_org_id"):
        op.create_index(
            "ix_architect_session_org_id",
            "architect_session",
            ["organization_id"],
        )
    if not _index_exists("ix_architect_message_session_id"):
        op.create_index(
            "ix_architect_message_session_id",
            "architect_message",
            ["session_id"],
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_architect_message_session_id")
    op.execute("DROP INDEX IF EXISTS ix_architect_session_org_id")
    op.execute("DROP INDEX IF EXISTS ix_architect_session_user_id")
    op.execute("DROP TABLE IF EXISTS architect_message")
    op.execute("DROP TABLE IF EXISTS architect_session")
