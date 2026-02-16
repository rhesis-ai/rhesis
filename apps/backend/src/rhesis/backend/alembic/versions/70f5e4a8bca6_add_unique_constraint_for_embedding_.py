"""add unique constraint for embedding deduplication

Revision ID: 70f5e4a8bca6
Revises: 2e3f4g5h6i7j
Create Date: 2026-02-12 17:26:18.000000

"""

from alembic import op
from typing import Union, Sequence


# revision identifiers, used by Alembic.
revision: str = "70f5e4a8bca6"
down_revision: Union[str, None] = "2e3f4g5h6i7j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint to prevent duplicate embeddings.

    This ensures that for a given entity with specific text, config, and status,
    only one embedding can exist per organization.
    """
    op.create_index(
        "uq_embedding_dedup",
        "embedding",
        ["organization_id", "entity_id", "entity_type", "config_hash", "text_hash", "status"],
        unique=True,
    )


def downgrade() -> None:
    """Remove the unique constraint."""
    op.drop_index("uq_embedding_dedup", table_name="embedding")
