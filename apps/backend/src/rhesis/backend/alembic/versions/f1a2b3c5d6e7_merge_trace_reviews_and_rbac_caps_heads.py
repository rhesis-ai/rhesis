"""Merge trace_reviews and rbac_caps parallel heads

Revision ID: f1a2b3c5d6e7
Revises: c0d1e2f3a4b5, d1e2f3a4b5c6
Create Date: 2026-07-02

d1e2f3a4b5c6 (add_trace_reviews_column) branched from c05814d9a399 and was
never merged into the main RBAC chain. This empty merge restores a single
head so ``alembic upgrade head`` is unambiguous again.
"""

from typing import Sequence, Union

revision: str = "f1a2b3c5d6e7"
down_revision: Union[str, None] = ("c0d1e2f3a4b5", "d1e2f3a4b5c6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
