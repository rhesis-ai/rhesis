from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5f354e261ce"
down_revision: Union[str, None] = "d22819b0aa66"
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
            comment="Embedding dimension (384, 768, 1024, or 1536). "
            "Only applicable for embedding models.",
        ),
    )


def downgrade() -> None:
    """Remove dimension column from model table."""
    op.drop_column("model", "dimension")
