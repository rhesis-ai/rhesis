"""create embedding table with multi-dimension support

Adds a dedicated Embedding table with multiple vector columns (384, 768, 1024, 1536 dimensions)
for storing embeddings from different models using HNSW indexes for fast similarity search.
Includes full-text search support with PostgreSQL TSVECTOR.

Revision ID: a1b2c3d4e5f8
Revises: 022c2c351b67
Create Date: 2026-01-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

import rhesis.backend.app.models.guid

revision: str = "a1b2c3d4e5f8"
down_revision: Union[str, None] = "022c2c351b67"
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
        # Embedding configuration
        sa.Column("embedding_config", sa.JSON(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        # Full-text search columns
        sa.Column("searchable_text", sa.Text(), nullable=False),
        sa.Column(
            "tsv",
            TSVECTOR,
            sa.Computed("to_tsvector('english', searchable_text)", persisted=True),
        ),
        sa.Column("text_hash", sa.String(64), nullable=False),
        # Ranking and metadata
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("origin", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        # Vector columns for different dimensions
        sa.Column("embedding_384", Vector(384), nullable=True),
        sa.Column("embedding_768", Vector(768), nullable=True),
        sa.Column("embedding_1024", Vector(1024), nullable=True),
        sa.Column("embedding_1536", Vector(1536), nullable=True),
        # Foreign keys
        sa.ForeignKeyConstraint(["model_id"], ["model.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        # Check constraint: exactly one vector column must be non-null
        sa.CheckConstraint(
            "(embedding_384 IS NOT NULL)::int + "
            "(embedding_768 IS NOT NULL)::int + "
            "(embedding_1024 IS NOT NULL)::int + "
            "(embedding_1536 IS NOT NULL)::int = 1",
            name="ck_embedding_exactly_one_embedding",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_embedding_id", "embedding", ["id"], unique=True)
    op.create_index("ix_embedding_deleted_at", "embedding", ["deleted_at"])
    op.create_index("ix_embedding_entity_id", "embedding", ["entity_id"])
    op.create_index("ix_embedding_entity_type", "embedding", ["entity_type"])
    op.create_index("ix_embedding_model_id", "embedding", ["model_id"])
    op.create_index("idx_embedding_entity", "embedding", ["entity_type", "entity_id"])
    op.create_index(
        "idx_embedding_entity_model", "embedding", ["entity_type", "entity_id", "model_id"]
    )

    # Partial indexes with WHERE clauses for active embeddings
    op.execute(
        """
        CREATE INDEX idx_active_model_config ON embedding (model_id, config_hash)
        WHERE status = 'active'
    """
    )
    op.execute(
        """
        CREATE INDEX idx_active_entity_model_config ON embedding
        (entity_type, model_id, config_hash)
        WHERE status = 'active'
    """
    )

    # GIN index for full-text search on tsv column
    op.create_index("idx_embedding_tsv", "embedding", ["tsv"], postgresql_using="gin")

    # Create HNSW vector similarity indexes for each dimension
    # HNSW provides better query performance than IVFFlat
    # Conservative parameters for fast builds with good quality:
    # - m: connections per layer (smaller values = faster builds)
    # - ef_construction: build quality (2x of m, diminishing returns after)

    # 384 dimensions
    op.execute(
        """
        CREATE INDEX idx_embedding_384 ON embedding
        USING hnsw (embedding_384 vector_cosine_ops)
        WITH (m = 8, ef_construction = 16)
        WHERE embedding_384 IS NOT NULL
    """
    )

    # 768 dimensions
    op.execute(
        """
        CREATE INDEX idx_embedding_768 ON embedding
        USING hnsw (embedding_768 vector_cosine_ops)
        WITH (m = 8, ef_construction = 16)
        WHERE embedding_768 IS NOT NULL
    """
    )

    # 1024 dimensions
    op.execute(
        """
        CREATE INDEX idx_embedding_1024 ON embedding
        USING hnsw (embedding_1024 vector_cosine_ops)
        WITH (m = 12, ef_construction = 24)
        WHERE embedding_1024 IS NOT NULL
    """
    )

    # 1536 dimensions
    op.execute(
        """
        CREATE INDEX idx_embedding_1536 ON embedding
        USING hnsw (embedding_1536 vector_cosine_ops)
        WITH (m = 12, ef_construction = 24)
        WHERE embedding_1536 IS NOT NULL
    """
    )


def downgrade() -> None:
    """Drop embedding table and indexes."""
    op.drop_table("embedding")
