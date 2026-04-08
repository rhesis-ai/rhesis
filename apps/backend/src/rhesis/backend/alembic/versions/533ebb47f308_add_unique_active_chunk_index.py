from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "533ebb47f308"
down_revision: Union[str, None] = "d22819b0aa66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_unique_active_chunk_index",
        "chunk",
        ["source_id", "chunk_index"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_unique_active_chunk_index", table_name="chunk")
