"""Add is_email_verified column to user table

Email verification status for sign-up flow, separate from is_verified
which is used for Polyphemus/admin access control.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a8
Create Date: 2026-02-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in the given table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("user", "is_email_verified"):
        op.add_column(
            "user",
            sa.Column(
                "is_email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    # Set is_email_verified=true for users migrated from Auth0 providers
    # (Google, GitHub, Auth0 email, etc. have all verified the email)
    connection = op.get_bind()
    connection.execute(
        text(
            """
            UPDATE "user" SET
                is_email_verified = true
            WHERE auth0_id IS NOT NULL
              AND is_email_verified = false
        """
        )
    )


def downgrade() -> None:
    op.drop_column("user", "is_email_verified")
