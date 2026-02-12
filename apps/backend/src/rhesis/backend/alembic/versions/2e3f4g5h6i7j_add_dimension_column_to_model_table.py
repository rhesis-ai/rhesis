"""add dimension column to model table

Revision ID: 2e3f4g5h6i7j
Revises: 1776e6dd47d3
Create Date: 2026-02-12 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence


# revision identifiers, used by Alembic.
revision: str = "2e3f4g5h6i7j"
down_revision: Union[str, None] = "1776e6dd47d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add dimension column to model table for embedding models."""
    op.add_column(
        "model",
        sa.Column(
            "dimension",
            sa.Integer(),
            nullable=True,
            comment="Embedding dimension (384, 768, 1024, or 1536). Only applicable for embedding models.",
        ),
    )


def downgrade() -> None:
    """Remove dimension column from model table."""
    op.drop_column("model", "dimension")
