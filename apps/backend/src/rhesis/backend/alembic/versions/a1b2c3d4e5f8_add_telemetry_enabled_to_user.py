"""add_telemetry_enabled_to_user

Revision ID: a1b2c3d4e5f8
Revises: a1b2c3d4e5f7
Create Date: 2025-10-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f8"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add telemetry_enabled column to user table.

    This column allows users to opt-in or opt-out of telemetry data collection.
    Default is FALSE (opt-in required) for privacy-first approach.
    """
    op.add_column(
        "user",
        sa.Column(
            "telemetry_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    # Create index for faster lookups
    op.create_index(
        "idx_user_telemetry_enabled",
        "user",
        ["telemetry_enabled"],
    )


def downgrade() -> None:
    """Remove telemetry_enabled column from user table"""
    op.drop_index("idx_user_telemetry_enabled", "user")
    op.drop_column("user", "telemetry_enabled")
