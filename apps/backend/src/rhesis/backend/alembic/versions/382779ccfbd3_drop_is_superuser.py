"""Drop is_superuser column from user table (SP8)

All references to is_superuser have been removed from the application code.
The initial admin's authority is now carried by the organization_member Owner
row created in the preceding backfill migration (e1f2a3b4c5d6).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "382779ccfbd3"
down_revision: Union[str, None] = "371c3c3cd787"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("user", "is_superuser")


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column("is_superuser", sa.Boolean(), nullable=True, server_default=sa.false()),
    )
