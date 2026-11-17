"""merge email verification deadline and requirement unlink heads

Revision ID: 72094f4a1948
Revises: c4e8a1f2d9b3, c4d8e1f2a3b6
Create Date: 2026-11-17

c4e8a1f2d9b3 and c4d8e1f2a3b6 were both written on top of b7e2d4a9c31f. This
empty merge joins the two tips so ``alembic upgrade head`` is unambiguous again.
"""

from typing import Sequence, Union

revision: str = "72094f4a1948"
down_revision: Union[str, None] = ("c4e8a1f2d9b3", "c4d8e1f2a3b6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
