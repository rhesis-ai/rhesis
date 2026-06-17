"""Add scopes JSONB column to token table (SP9 token scoping).

API tokens can now carry an explicit permission subset.  When set, the EE
authorization provider intersects the token's scopes with the issuing
user's effective permissions so a token can never exceed its owner's access.
Community tier ignores scopes (but stores them for forward-compatibility).

Revision ID: 7d8e9f0a1b2c
Revises: 6c7d8e9f0a1b
Create Date: 2026-06-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7d8e9f0a1b2c"
down_revision: Union[str, None] = "6c7d8e9f0a1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "token",
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Optional explicit permission subset for this token. "
                "When set (a JSON array of capability strings), the EE "
                "provider intersects with the owner's effective permissions — "
                "the token can never exceed its issuer. NULL means the token "
                "inherits the owner's full access (community-tier behaviour)."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("token", "scopes")
