"""add_terms_acceptance_to_user

Revision ID: b8c9d0e1f2a3
Revises: a7c3e9f10b24
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7c3e9f10b24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column("terms_accepted_version", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "terms_accepted_version")
    op.drop_column("user", "terms_accepted_at")
