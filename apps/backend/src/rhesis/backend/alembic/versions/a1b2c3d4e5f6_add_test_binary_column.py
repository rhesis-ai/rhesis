"""Add test_binary column to test table

Revision ID: a1b2c3d4e5f6
Revises: 78a3f23a9d29
Create Date: 2026-01-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "78a3f23a9d29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add test_binary column for storing image data
    # MIME type is stored in test_metadata JSONB column as 'binary_mime_type' key
    op.add_column("test", sa.Column("test_binary", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("test", "test_binary")
