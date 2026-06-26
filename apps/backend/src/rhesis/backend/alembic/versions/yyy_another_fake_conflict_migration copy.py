"""fake conflict migration for testing

Revision ID: yyy111fakeid
Revises: zzz999fakeid
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "yyy111fakeid"
down_revision: Union[str, None] = "zzz999fakeid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
