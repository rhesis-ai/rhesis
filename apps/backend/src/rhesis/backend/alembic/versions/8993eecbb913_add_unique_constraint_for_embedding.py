from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8993eecbb913"
down_revision: Union[str, None] = "c5f354e261ce"
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
        ["organization_id", "entity_id", "entity_type", "config_hash", "text_hash", "status_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove the unique constraint."""
    op.drop_index("uq_embedding_dedup", table_name="embedding")
