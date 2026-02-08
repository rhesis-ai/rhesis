"""Add auth provider columns for native authentication

This migration adds columns to support native authentication providers,
replacing the Auth0-specific auth0_id column with a more flexible
provider-agnostic approach.

Revision ID: a1c2d3e4f5g6
Revises: 022c2c351b67
Create Date: 2026-01-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "a1c2d3e4f5g6"
down_revision: Union[str, None] = "022c2c351b67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in the given table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def _index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index already exists on the given table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    # Add new columns for provider-agnostic authentication (idempotent)
    if not _column_exists("user", "provider_type"):
        op.add_column(
            "user",
            sa.Column(
                "provider_type",
                sa.String(50),
                nullable=True,
                comment=("Authentication provider type (google, github, email, etc.)"),
            ),
        )

    if not _column_exists("user", "external_provider_id"):
        op.add_column(
            "user",
            sa.Column(
                "external_provider_id",
                sa.String(255),
                nullable=True,
                comment=("External ID from the authentication provider"),
            ),
        )

    if not _column_exists("user", "password_hash"):
        op.add_column(
            "user",
            sa.Column(
                "password_hash",
                sa.String(255),
                nullable=True,
                comment=("Bcrypt password hash for email/password authentication"),
            ),
        )

    # Create index on provider_type for efficient filtering
    if not _index_exists("user", "ix_user_provider_type"):
        op.create_index(
            "ix_user_provider_type",
            "user",
            ["provider_type"],
            unique=False,
        )

    # Create composite index for provider lookups
    if not _index_exists("user", "ix_user_provider_external_id"):
        op.create_index(
            "ix_user_provider_external_id",
            "user",
            ["provider_type", "external_provider_id"],
            unique=False,
        )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_user_provider_external_id", table_name="user")
    op.drop_index("ix_user_provider_type", table_name="user")

    # Drop columns
    op.drop_column("user", "password_hash")
    op.drop_column("user", "external_provider_id")
    op.drop_column("user", "provider_type")
