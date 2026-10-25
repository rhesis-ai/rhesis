"""Merge ClickUp and run duration migrations.

Revision ID: 1d3218c24167
Revises: c3e5cfa15f16, e5a1c7d93b42
Create Date: 2026-10-25
"""

from typing import Sequence, Union

revision: str = "1d3218c24167"
down_revision: Union[str, Sequence[str], None] = (
    "c3e5cfa15f16",
    "e5a1c7d93b42",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
