"""fake conflict migration for testing

Revision ID: zzz999fakeid
Revises: b1c2d3e4f5a6
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "zzz999fakeid"
down_revision: Union[str, None] = "yyy111fakeid"  # wrong, not existing id
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
