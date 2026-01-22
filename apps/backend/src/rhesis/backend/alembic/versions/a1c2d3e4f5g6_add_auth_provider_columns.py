"""Add auth provider columns for native authentication

This migration adds columns to support native authentication providers,
replacing the Auth0-specific auth0_id column with a more flexible
provider-agnostic approach.

Revision ID: a1c2d3e4f5g6
Revises: 1dc33ff4b0a2
Create Date: 2026-01-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c2d3e4f5g6"
down_revision: Union[str, None] = "1dc33ff4b0a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns for provider-agnostic authentication
    op.add_column(
        "user",
        sa.Column(
            "provider_type",
            sa.String(50),
            nullable=True,
            comment="Authentication provider type (google, github, email, etc.)",
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "external_provider_id",
            sa.String(255),
            nullable=True,
            comment="External ID from the authentication provider",
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "password_hash",
            sa.String(255),
            nullable=True,
            comment="Bcrypt password hash for email/password authentication",
        ),
    )

    # Create index on provider_type for efficient filtering
    op.create_index(
        "ix_user_provider_type",
        "user",
        ["provider_type"],
        unique=False,
    )

    # Create composite index for provider lookups
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
