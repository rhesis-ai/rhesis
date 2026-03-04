"""create file table for test input/output files

Adds a File table for storing binary file attachments (images, PDFs, audio)
associated with Tests (input files) and TestResults (output files) using
a polymorphic entity_id + entity_type pattern.

Revision ID: b3f7a9c2d1e4
Revises: aef6c47a8faa
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import rhesis.backend.app.models.guid

revision: str = "b3f7a9c2d1e4"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create file table with indexes."""
    op.create_table(
        "file",
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        # File content (binary)
        sa.Column("content", sa.LargeBinary(), nullable=True),
        # File metadata
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Polymorphic entity reference
        sa.Column(
            "entity_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        # Ordering
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        # Multi-tenancy
        sa.Column(
            "organization_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=True,
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index("ix_file_id", "file", ["id"], unique=True)
    op.create_index("ix_file_nano_id", "file", ["nano_id"], unique=True)
    op.create_index("ix_file_deleted_at", "file", ["deleted_at"])
    op.create_index("ix_file_entity_id", "file", ["entity_id"])
    op.create_index("ix_file_entity_type", "file", ["entity_type"])
    # Composite index for polymorphic lookups
    op.create_index(
        "idx_file_entity",
        "file",
        ["entity_id", "entity_type"],
    )


def downgrade() -> None:
    """Drop file table and indexes."""
    op.drop_table("file")
