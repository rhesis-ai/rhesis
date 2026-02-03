from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, CheckConstraint, Column, Computed, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import ActivityTrackableMixin, OrganizationAndUserMixin


class EmbeddingConfig:
    """Configuration for embedding dimensions"""

    SUPPORTED_DIMENSIONS = {
        384: "embedding_384",
        768: "embedding_768",
        1024: "embedding_1024",
        1536: "embedding_1536",
    }

    @classmethod
    def get_dimension_from_config(cls, config: dict) -> int:
        """Extract dimension from embedding_config JSON"""
        if not config or "dimension" not in config:
            raise ValueError("Invalid embedding configuration")

        dimension = config["dimension"]

        cls.validate_dimension(dimension)
        return dimension

    @classmethod
    def validate_dimension(cls, dimension: int) -> None:
        if dimension not in cls.SUPPORTED_DIMENSIONS:
            raise ValueError(
                f"Dimension {dimension} not supported. "
                f"Supported: {sorted(cls.SUPPORTED_DIMENSIONS.keys())}"
            )


class Embedding(Base, ActivityTrackableMixin, OrganizationAndUserMixin):
    __tablename__ = "embedding"

    # Polymorphic entity reference (Test, Source, etc.)
    entity_id = Column(GUID(), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)

    # Model that generated this embedding
    model_id = Column(GUID(), ForeignKey("model.id"), nullable=False, index=True)
    model = relationship("Model", backref="embeddings")

    # The exact configuration used to generate this embedding
    # You need to decide what needs to be stored here
    embedding_config = Column(
        JSON, nullable=False, doc="Stores all parameters used to generate the embedding"
    )
    config_hash = Column(String(64), nullable=False)

    # Text for full-text search
    searchable_text = Column(Text, nullable=False)
    tsv = Column(
        TSVECTOR,
        Computed("to_tsvector('english', searchable_text)", persisted=True),
        doc="Generated column for GIN full-text search index",
    )
    text_hash = Column(String(64), nullable=False)

    # Ranking and metadata
    weight = Column("weight", nullable=False, default=1.0)
    origin = Column(String(20), doc="Origin of the content: 'user', 'generated', 'imported'")
    status = Column(String(20), default="active", doc="Lifecycle status of the embedding")

    # Multiple embedding columns for different dimensions
    embedding_384 = Column(Vector(384), nullable=True)
    embedding_768 = Column(Vector(768), nullable=True)
    embedding_1024 = Column(Vector(1024), nullable=True)
    embedding_1536 = Column(Vector(1536), nullable=True)

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "(embedding_384 IS NOT NULL)::int + "
            "(embedding_768 IS NOT NULL)::int + "
            "(embedding_1024 IS NOT NULL)::int + "
            "(embedding_1536 IS NOT NULL)::int = 1",
            name="ck_embedding_exactly_one_embedding",
        ),
        # Cross-entity-type search: model_id, config_hash, and status
        Index(
            "idx_active_model_config",
            "model_id",
            "config_hash",
            postgresql_where=Column("status") == "active",
        ),
        # Search within entity type: entity_type, model_id, config_hash, and status
        Index(
            "idx_active_entity_model_config",
            "entity_type",
            "model_id",
            "config_hash",
            postgresql_where=Column("status") == "active",
        ),
    )

    @property
    def embedding(self) -> Optional[List[float]]:
        """
        Get the actual embedding from the appropriate column.
        Returns None if no embedding is stored yet.

        Raises:
            ValueError: If embedding_config is not set or invalid

        Example:
            >>> emb = session.query(Embedding).first()
            >>> vector = emb.embedding  # Automatically reads from correct column
            >>> if vector:
            ...     print(len(vector))
            768
        """
        if not self.embedding_config:
            raise ValueError(
                "Embedding configuration is not set. Cannot determine which column to read from."
            )

        dimension = EmbeddingConfig.get_dimension_from_config(self.embedding_config)
        column_name = EmbeddingConfig.SUPPORTED_DIMENSIONS.get(dimension)

        if not column_name:
            raise ValueError(f"Dimension {dimension} not in SUPPORTED_DIMENSIONS")

        return getattr(self, column_name, None)

    @embedding.setter
    def embedding(self, value: List[float]) -> None:
        """
        Set the embedding in the appropriate column based on vector dimension.
        The dimension must match the one specified in embedding_config.

        Args:
            value: Vector to store (cannot be None)

        Raises:
            ValueError: If embedding_config is not set,
            vector dimensions doesn't match embedding_config, or dimension is not supported

        Example:
            >>> emb = Embedding(embedding_config={"dimension": 768, ...})
            >>> emb.embedding = [0.1] * 768  # Automatically stored in embedding_768
        """
        if not self.embedding_config:
            raise ValueError(
                "embedding_config must be set before assigning embedding. "
                "Set embedding_config with dimension, model, and other parameters first."
            )

        expected_dimension = EmbeddingConfig.get_dimension_from_config(self.embedding_config)
        actual_dimension = len(value)

        if actual_dimension != expected_dimension:
            raise ValueError(
                f"Vector dimension mismatch: vector has {actual_dimension} dimensions "
                f"but embedding_config specifies {expected_dimension}. "
                "Update embedding_config first if you want to store a different dimension."
            )

        # Clear all embedding columns
        for col_name in EmbeddingConfig.SUPPORTED_DIMENSIONS.values():
            setattr(self, col_name, None)

        # Set the appropriate column
        column_name = EmbeddingConfig.SUPPORTED_DIMENSIONS[expected_dimension]
        setattr(self, column_name, value)

    @property
    def dimension(self) -> int:
        """
        Get the dimension size from embedding_config.
        This represents what dimension the embedding SHOULD have.

        Raises:
            ValueError: If embedding_config is not set or invalid

        Example:
            >>> emb.embedding_config = {"dimension": 768, ...}
            >>> emb.dimension
            768
        """
        if not self.embedding_config or "dimension" not in self.embedding_config:
            raise ValueError("Embedding configuration is not set")

        dimension = EmbeddingConfig.get_dimension_from_config(self.embedding_config)
        return dimension

    @property
    def active_dimension(self) -> Optional[int]:
        """
        Returns the dimension of the currently stored embedding by inspecting
        which column actually has data, regardless of what the config says.

        This is more reliable than reading from config since it reflects
        what's actually in the database.

        Returns:
            The dimension (384, 768, 1024, or 1536) or None if no embedding stored

        Example:
            >>> emb = Embedding(embedding_config={"dimension": 768})
            >>> emb.embedding = [0.1] * 768
            >>> emb.active_dimension  # Returns: 768
            >>> emb.embedding_768 = None  # Manually clear
            >>> emb.active_dimension  # Returns: None
        """
        for dim, col_name in EmbeddingConfig.SUPPORTED_DIMENSIONS.items():
            if getattr(self, col_name, None) is not None:
                return dim
        return None

    @property
    def embedding_column_name(self) -> Optional[str]:
        """Returns the name of the active embedding column"""
        if dim := self.active_dimension:
            return EmbeddingConfig.SUPPORTED_DIMENSIONS[dim]
        return None

    def __repr__(self) -> str:
        """String representation for debugging"""
        dim = self.active_dimension or "none"
        return (
            f"<Embedding(id={self.id}, entity_type={self.entity_type}, "
            f"entity_id={self.entity_id}, dimension={dim}, status={self.status})>"
        )
