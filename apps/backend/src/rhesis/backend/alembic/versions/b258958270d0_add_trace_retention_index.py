"""Add trace retention index (organization_id, created_at).

The trace retention sweep (jobs/trace_retention.py) hard-deletes rows
per org filtered by created_at. Without this composite index the sweep
would need a sequential scan per org on every run.

Revision ID: b258958270d0
Revises: ff71b040aebf
Create Date: 2026-09-01
"""

from typing import Union

from alembic import op

revision: str = "b258958270d0"
down_revision: Union[str, None] = "ff71b040aebf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_trace_org_created",
        "trace",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_trace_org_created", table_name="trace")
