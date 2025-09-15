from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c5e102239786"
down_revision: Union[str, None] = "17eaea1d50ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add test_metadata column to test table
    op.add_column(
        "test", sa.Column("test_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    # Remove test_metadata column from test table
    op.drop_column("test", "test_metadata")
