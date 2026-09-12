"""add test_parameters column

Revision ID: c3a4b5d6e7f8
Revises: b7e1c9d4a2f3
Create Date: 2026-09-12

"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3a4b5d6e7f8"
down_revision: Union[str, None] = "b7e1c9d4a2f3"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "test",
        sa.Column("test_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("test", "test_parameters")
