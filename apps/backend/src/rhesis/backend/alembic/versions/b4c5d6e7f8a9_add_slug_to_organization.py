"""add_slug_to_organization

Add slug column to the organization table for human-readable SSO login URLs.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization",
        sa.Column("slug", sa.String(50), nullable=True),
    )
    op.create_index("ix_organization_slug", "organization", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_organization_slug", table_name="organization")
    op.drop_column("organization", "slug")
