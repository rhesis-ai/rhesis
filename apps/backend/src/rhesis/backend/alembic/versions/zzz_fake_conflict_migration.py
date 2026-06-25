"""fake conflict migration for testing

Revision ID: zzz999fakeid
Revises: 6a7b8c9d0e1f
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "zzz999fakeid"
down_revision: Union[str, None] = "6a7b8c9d0e1f"  # old revision, not the current HEAD
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
