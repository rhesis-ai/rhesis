"""add architect session and message tables

Revision ID: c4d8e2f1a3b5
Revises: b3f7a9c2d1e4
Create Date: 2026-03-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import rhesis.backend

# revision identifiers, used by Alembic.
revision: str = "c4d8e2f1a3b5"
down_revision: Union[str, None] = "b3f7a9c2d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.create_index(
        "ix_architect_session_user_id",
        "architect_session",
        ["user_id"],
    )
    op.create_index(
        "ix_architect_session_org_id",
        "architect_session",
        ["organization_id"],
    )
    op.create_index(
        "ix_architect_message_session_id",
        "architect_message",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_architect_message_session_id")
    op.drop_index("ix_architect_session_org_id")
    op.drop_index("ix_architect_session_user_id")
    op.drop_table("architect_message")
    op.drop_table("architect_session")
