"""add_test_reviews_column

Revision ID: f8b3c9d4e5a6
Revises: 04720d11891c
Create Date: 2025-10-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f8b3c9d4e5a6"
down_revision: Union[str, None] = "04720d11891c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add test_reviews column for human feedback on test results.

    The test_reviews column stores human evaluations as JSONB with structure:
    - metadata: Summary info (last_updated_at, last_updated_by, total_reviews, etc.)
    - reviews: Array of review objects with created_at/updated_at timestamps

    This enables tracking multiple reviewers and review edits over time.
    """
    # Add test_reviews column (nullable for existing records)
    op.add_column(
        "test_result",
        sa.Column("test_reviews", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove test_reviews column."""
    op.drop_column("test_result", "test_reviews")
