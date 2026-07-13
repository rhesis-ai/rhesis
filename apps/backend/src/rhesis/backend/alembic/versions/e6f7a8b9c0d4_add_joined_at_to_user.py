"""Add joined_at to user

Tracks when a user first became an active organization member (accepted
invite or org-founder attachment). Distinct from last_login_at, which updates
on every authentication.

Revision ID: e6f7a8b9c0d4
Revises: d5e6f7a8b9c3
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d4"
down_revision: Union[str, None] = "d5e6f7a8b9c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the user first became an active organization member",
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET joined_at = last_login_at
            WHERE organization_id IS NOT NULL
              AND joined_at IS NULL
              AND last_login_at IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("user", "joined_at")
