from sqlalchemy import Column, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import EmbeddableMixin, OrganizationAndUserMixin


class Chunk(
    Base,
    EmbeddableMixin,
    OrganizationAndUserMixin,
):
    __tablename__ = "chunk"

    source_id = Column(GUID(), ForeignKey("source.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=False)
    chunk_metadata = Column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status_id = Column(GUID(), ForeignKey("status.id"))

    # Relationships
    source = relationship("Source", back_populates="chunks")
    status = relationship("Status", back_populates="chunks")
    user = relationship("User", foreign_keys="[Chunk.user_id]", back_populates="created_chunks")

    __table_args__ = (
        Index(
            "ix_unique_active_chunk_index",
            "source_id",
            "chunk_index",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def to_searchable_text(self) -> str:
        """Generate searchable text from chunk fields for embeddings and full-text search"""
        return self.content
