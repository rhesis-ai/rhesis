"""add_is_verified_to_user

Adds is_verified column to the user table to track if the user is verified or not.

Revision ID: faad9078ee78
Revises: 0da7faeee4f5
Create Date: 2025-12-01 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "faad9078ee78"
down_revision: Union[str, None] = "0da7faeee4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade() -> None:
    op.drop_column("user", "is_verified")
