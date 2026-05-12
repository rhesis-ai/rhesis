"""merge embedding table and SSO slug migration heads

Revision ID: 8f2e4a9c1d3b
Revises: a1b2c3d4e5f8, b4c5d6e7f8a9
Create Date: 2026-05-12

Brings together main's embedding-table migration and the SSO org slug branch.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "8f2e4a9c1d3b"
down_revision: Union[str, None] = ("a1b2c3d4e5f8", "b4c5d6e7f8a9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
