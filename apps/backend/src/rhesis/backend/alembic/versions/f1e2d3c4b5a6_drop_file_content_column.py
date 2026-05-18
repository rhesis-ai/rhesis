"""drop file content column

Removes the legacy bytea content column from the file table.

Apply this revision after deploying the new storage-backed code and
verifying that no application path reads from File.content.

Revision ID: f1e2d3c4b5a6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, None] = "9b25f353e9c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if _column_exists("file", "content"):
        op.drop_column("file", "content")


def downgrade() -> None:
    op.add_column(
        "file",
        sa.Column("content", sa.LargeBinary(), nullable=True),
    )
