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


def upgrade() -> None:
    op.drop_column("file", "content")


def downgrade() -> None:
    op.add_column(
        "file",
        sa.Column("content", sa.LargeBinary(), nullable=True),
    )
