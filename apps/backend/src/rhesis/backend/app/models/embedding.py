from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import ActivityTrackableMixin, OrganizationAndUserMixin


class Embedding(Base, ActivityTrackableMixin, OrganizationAndUserMixin):
    __tablename__ = "embedding"

    # Polymorphic entity reference (Test, Source, etc.)
    entity_id = Column(GUID(), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)

    # Model that generated this embedding
    model_id = Column(GUID(), ForeignKey("model.id"), nullable=False)

    # Multiple vector columns for different dimensions
    vector_768 = Column(Vector(768), nullable=True)
    vector_1536 = Column(Vector(1536), nullable=True)
    vector_3072 = Column(Vector(3072), nullable=True)

    # Metadata
    content_hash = Column(String(64))  # SHA256 of embedded content
    status = Column(String(20), default="active")

    # Relationships
    model = relationship("Model", backref="embeddings")

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "(vector_768 IS NOT NULL)::int + "
            "(vector_1536 IS NOT NULL)::int + "
            "(vector_3072 IS NOT NULL)::int = 1",
            name="ck_embedding_exactly_one_vector",
        ),
        Index("idx_embedding_entity", "entity_type", "entity_id"),
        Index("idx_embedding_entity_model", "entity_type", "entity_id", "model_id"),
        Index("idx_embedding_active", "entity_type", "status"),
    )

    @hybrid_property
    def vector(self):
        """Get the actual vector regardless of dimension"""
        if self.vector_768 is not None:
            return self.vector_768
        elif self.vector_1536 is not None:
            return self.vector_1536
        elif self.vector_3072 is not None:
            return self.vector_3072
        return None

    @hybrid_property
    def dimensions(self):
        """Get the dimension size of the stored vector"""
        if self.vector_768 is not None:
            return 768
        elif self.vector_1536 is not None:
            return 1536
        elif self.vector_3072 is not None:
            return 3072
        return None
