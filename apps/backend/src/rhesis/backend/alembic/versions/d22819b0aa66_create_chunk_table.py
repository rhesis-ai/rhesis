"""create chunk table

Revision ID: d22819b0aa66
Revises: 5b3d40e898ff
Create Date: 2026-03-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import rhesis.backend.app.models.guid
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_status_template,
    load_cleanup_type_lookup_template,
    load_status_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "d22819b0aa66"
down_revision: Union[str, None] = "5b3d40e898ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chunk table with indexes."""
    op.create_table(
        "chunk",
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
        # Foreign Keys
        sa.Column(
            "source_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=False,
        ),
        sa.Column(
            "status_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=True,
        ),
        # Chunk content and metadata
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "chunk_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
        # Constraints
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["source.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["status_id"],
            ["status.id"],
            ondelete="SET NULL",
        ),
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
    op.create_index("ix_chunk_id", "chunk", ["id"], unique=True)
    op.create_index("ix_chunk_nano_id", "chunk", ["nano_id"], unique=True)
    op.create_index("ix_chunk_deleted_at", "chunk", ["deleted_at"])
    op.create_index("ix_chunk_source_id", "chunk", ["source_id"])

    # Add EntityType entry for Chunk for existing organizations
    entity_type_values = """
        ('EntityType', 'Chunk', 'Entity type for chunks')
    """

    chunk_status_values = """
        ('Active', 'Chunk is active and usable', 'Chunk')
    """

    # Insert EntityType entry for Chunk
    entity_type_sql = load_type_lookup_template(entity_type_values)
    op.execute(entity_type_sql)

    # Insert Chunk status entries
    chunk_status_sql = load_status_template("EntityType", "Chunk", chunk_status_values)
    op.execute(chunk_status_sql)


def downgrade() -> None:
    """Drop chunk table and indexes."""
    chunk_status_cleanup_values = """
        ('Active')
    """

    entity_type_cleanup_values = """
        ('Chunk')
    """

    # Clean up Chunk status entries
    status_cleanup_sql = load_cleanup_status_template(
        "EntityType", "Chunk", chunk_status_cleanup_values
    )
    op.execute(status_cleanup_sql)

    # Clean up EntityType entry for Chunk
    entity_cleanup_sql = load_cleanup_type_lookup_template("EntityType", entity_type_cleanup_values)
    op.execute(entity_cleanup_sql)

    op.drop_table("chunk")
