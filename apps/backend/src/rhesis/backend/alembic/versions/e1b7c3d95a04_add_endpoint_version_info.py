"""add endpoint version_info column

Revision ID: e1b7c3d95a04
Revises: a0a48c28ad64
Create Date: 2026-09-16

"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e1b7c3d95a04"
down_revision: Union[str, None] = "a0a48c28ad64"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "endpoint",
        sa.Column("version_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("endpoint", "version_info")
