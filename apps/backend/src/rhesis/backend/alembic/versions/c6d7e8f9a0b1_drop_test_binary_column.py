"""drop test binary column

Removes the legacy bytea ``test_binary`` column from the ``test`` table.
It is an orphan from before the file storage migration: no ORM model
references it, no application code reads or writes it, but ~38 MB of
leftover binary data still lives in 10 rows.

Revision ID: c6d7e8f9a0b1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ``test_binary`` is an orphan column that was never created by any
    # prior Alembic migration — it lives only in long-running production
    # databases. On fresh databases (CI, new test runs, new dev installs)
    # the column does not exist, so the drop must be conditional or the
    # migration breaks every fresh schema bootstrap.
    op.execute("ALTER TABLE test DROP COLUMN IF EXISTS test_binary")


def downgrade() -> None:
    op.add_column(
        "test",
        sa.Column("test_binary", sa.LargeBinary(), nullable=True),
    )
