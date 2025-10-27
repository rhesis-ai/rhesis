"""add_token_hash_column

Revision ID: 024a24c97022
Revises: e364aaec703f
Create Date: 2025-10-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "024a24c97022"
down_revision: Union[str, None] = "e364aaec703f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add token_hash column for efficient token lookups.

    The token_hash column stores a SHA-256 hash of the token value,
    allowing O(1) indexed lookups without decrypting all tokens.
    """
    # Add token_hash column (nullable initially for data migration)
    op.add_column("token", sa.Column("token_hash", sa.String(length=64), nullable=True))

    # Note: The column is nullable=True initially to allow backfilling existing data
    # After data migration, a separate migration should set nullable=False


def downgrade() -> None:
    """Remove token_hash column."""
    op.drop_column("token", "token_hash")
