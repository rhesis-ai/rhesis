"""create embedding table with multi-dimension support

Adds a dedicated Embedding table with multiple vector columns (768, 1536, 3072 dimensions)
for storing embeddings from different models using HNSW indexes for fast similarity search.

Revision ID: a1b2c3d4e5f8
Revises: c9d8e7f6a5b4
Create Date: 2026-01-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

import rhesis.backend.app.models.guid

revision: str = "a1b2c3d4e5f8"
down_revision: Union[str, None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create embedding table and pgvector extension."""

    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create embedding table
    op.create_table(
        "embedding",
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        # Polymorphic entity reference
        sa.Column("entity_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        # Model reference
        sa.Column("model_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        # Multi-tenancy
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column("user_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        # Vector columns for different dimensions
        sa.Column("vector_768", Vector(768), nullable=True),
        sa.Column("vector_1536", Vector(1536), nullable=True),
        sa.Column("vector_3072", Vector(3072), nullable=True),
        # Metadata
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        # Foreign keys
        sa.ForeignKeyConstraint(["model_id"], ["model.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        # Check constraint: exactly one vector column must be non-null
        sa.CheckConstraint(
            "(vector_768 IS NOT NULL)::int + "
            "(vector_1536 IS NOT NULL)::int + "
            "(vector_3072 IS NOT NULL)::int = 1",
            name="ck_embedding_exactly_one_vector",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_embedding_id", "embedding", ["id"], unique=True)
    op.create_index("ix_embedding_deleted_at", "embedding", ["deleted_at"])
    op.create_index("ix_embedding_entity_id", "embedding", ["entity_id"])
    op.create_index("ix_embedding_entity_type", "embedding", ["entity_type"])
    op.create_index("idx_embedding_entity", "embedding", ["entity_type", "entity_id"])
    op.create_index(
        "idx_embedding_entity_model", "embedding", ["entity_type", "entity_id", "model_id"]
    )
    op.create_index("idx_embedding_active", "embedding", ["entity_type", "status"])

    # Create HNSW vector similarity indexes for each dimension
    # HNSW provides better query performance than IVFFlat
    # Conservative parameters for fast builds with good quality:
    # - m: connections per layer (smaller values = faster builds)
    # - ef_construction: build quality (2x of m, diminishing returns after)

    # 768 dimensions (Vertex AI text-embedding-005)
    op.execute(
        """
        CREATE INDEX idx_embedding_vector_768 ON embedding
        USING hnsw (vector_768 vector_cosine_ops)
        WITH (m = 8, ef_construction = 16)
        WHERE vector_768 IS NOT NULL
    """
    )

    # 1536 dimensions (OpenAI text-embedding-3-small)
    op.execute(
        """
        CREATE INDEX idx_embedding_vector_1536 ON embedding
        USING hnsw (vector_1536 vector_cosine_ops)
        WITH (m = 12, ef_construction = 24)
        WHERE vector_1536 IS NOT NULL
    """
    )

    # 3072 dimensions (OpenAI text-embedding-3-large or gemini-embeddin-g001)
    op.execute(
        """
        CREATE INDEX idx_embedding_vector_3072 ON embedding
        USING hnsw (vector_3072 vector_cosine_ops)
        WITH (m = 16, ef_construction = 32)
        WHERE vector_3072 IS NOT NULL
    """
    )


def downgrade() -> None:
    """Drop embedding table and indexes."""
    op.drop_table("embedding")
