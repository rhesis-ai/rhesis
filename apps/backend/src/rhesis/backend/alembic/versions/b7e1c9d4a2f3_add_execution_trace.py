"""add execution_trace table

Revision ID: b7e1c9d4a2f3
Revises: f2b3c4d5e6a7
Create Date: 2026-08-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

import rhesis.backend.app.models.guid

# revision identifiers, used by Alembic.
revision: str = "b7e1c9d4a2f3"
down_revision: Union[str, None] = "f2b3c4d5e6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execution_trace",
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nano_id", sa.String(12), unique=True, nullable=False),
        sa.Column("project_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("function_name", sa.String(length=255), nullable=False),
        sa.Column("inputs", JSONB(), nullable=False),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_execution_trace_project_id"), "execution_trace", ["project_id"])
    op.create_index(
        op.f("ix_execution_trace_organization_id"), "execution_trace", ["organization_id"]
    )
    op.create_index(op.f("ix_execution_trace_environment"), "execution_trace", ["environment"])
    op.create_index(op.f("ix_execution_trace_function_name"), "execution_trace", ["function_name"])
    op.create_index(op.f("ix_execution_trace_status"), "execution_trace", ["status"])
    op.create_index(op.f("ix_execution_trace_executed_at"), "execution_trace", ["executed_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_trace_executed_at"), table_name="execution_trace")
    op.drop_index(op.f("ix_execution_trace_status"), table_name="execution_trace")
    op.drop_index(op.f("ix_execution_trace_function_name"), table_name="execution_trace")
    op.drop_index(op.f("ix_execution_trace_environment"), table_name="execution_trace")
    op.drop_index(op.f("ix_execution_trace_organization_id"), table_name="execution_trace")
    op.drop_index(op.f("ix_execution_trace_project_id"), table_name="execution_trace")
    op.drop_table("execution_trace")
