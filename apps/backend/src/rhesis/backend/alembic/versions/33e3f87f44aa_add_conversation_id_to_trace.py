"""add conversation_id to trace

Revision ID: 33e3f87f44aa
Revises: 554e3e207a3f
Create Date: 2026-02-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "33e3f87f44aa"
down_revision: Union[str, None] = "554e3e207a3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add conversation_id column and composite index to trace table."""
    op.add_column(
        "trace",
        sa.Column("conversation_id", sa.String(255), nullable=True),
    )
    # Composite index covers single-column lookups on conversation_id
    # so a separate single-column index is not needed
    op.create_index(
        "idx_trace_conversation",
        "trace",
        ["conversation_id", sa.text("start_time DESC")],
    )


def downgrade() -> None:
    """Remove conversation_id column and index from trace table."""
    op.drop_index("idx_trace_conversation", table_name="trace")
    op.drop_column("trace", "conversation_id")
