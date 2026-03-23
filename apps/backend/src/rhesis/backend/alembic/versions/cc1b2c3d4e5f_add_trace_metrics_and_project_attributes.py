"""Add trace metrics columns and project attributes

Revision ID: cc1b2c3d4e5f
Revises: 5b3d40e898ff
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import rhesis.backend.app.models.guid

revision: str = "cc1b2c3d4e5f"
down_revision: Union[str, None] = "5b3d40e898ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trace", sa.Column("trace_metrics", postgresql.JSONB(), nullable=True))
    op.add_column(
        "trace",
        sa.Column(
            "trace_metrics_status_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=True,
        ),
    )
    op.add_column("trace", sa.Column("trace_metrics_processed_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_trace_trace_metrics_status",
        "trace",
        "status",
        ["trace_metrics_status_id"],
        ["id"],
    )
    op.create_index(
        "idx_trace_trace_metrics_status",
        "trace",
        ["trace_metrics_status_id"],
    )
    op.create_index(
        "idx_trace_metrics_unprocessed",
        "trace",
        ["created_at"],
        postgresql_where=sa.text("trace_metrics_processed_at IS NULL"),
        if_not_exists=True,
    )

    op.add_column("project", sa.Column("attributes", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("project", "attributes")

    op.drop_index("idx_trace_metrics_unprocessed", table_name="trace")
    op.drop_index("idx_trace_trace_metrics_status", table_name="trace")
    op.drop_constraint("fk_trace_trace_metrics_status", "trace", type_="foreignkey")
    op.drop_column("trace", "trace_metrics_processed_at")
    op.drop_column("trace", "trace_metrics_status_id")
    op.drop_column("trace", "trace_metrics")
