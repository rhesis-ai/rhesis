"""add file storage columns

Adds storage_path, content_hash, extracted_text, and extraction_status columns
to the file table as part of the cloud-run-large-files migration.

The content column is NOT dropped here — a follow-up Alembic revision
(applied at runbook step 7 after soak) will drop it.

Revision ID: 9b25f353e9c8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9b25f353e9c8"
down_revision: Union[str, None] = "fe4a8b2c9d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("file", sa.Column("storage_path", sa.String(length=512), nullable=True))
    op.add_column("file", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("file", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column(
        "file",
        sa.Column(
            "extraction_status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("file", "extraction_status")
    op.drop_column("file", "extracted_text")
    op.drop_column("file", "content_hash")
    op.drop_column("file", "storage_path")
