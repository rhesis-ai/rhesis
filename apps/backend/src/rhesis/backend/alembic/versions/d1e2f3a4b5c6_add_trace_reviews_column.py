"""add_trace_reviews_column

Revision ID: d1e2f3a4b5c6
Revises: c05814d9a399
Create Date: 2026-03-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c05814d9a399"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trace_reviews column for human feedback on trace evaluations.

    Same JSONB structure as test_result.test_reviews:
    - metadata: Summary info (last_updated_at, last_updated_by, total_reviews, etc.)
    - reviews: Array of review objects with created_at/updated_at timestamps
    """
    op.add_column(
        "trace",
        sa.Column("trace_reviews", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove trace_reviews column."""
    op.drop_column("trace", "trace_reviews")
