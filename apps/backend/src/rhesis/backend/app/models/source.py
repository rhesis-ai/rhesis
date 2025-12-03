from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import deferred, relationship

from .base import Base
from .guid import GUID
from .mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
    OrganizationAndUserMixin,
    TagsMixin,
)


class Source(
    Base, ActivityTrackableMixin, OrganizationAndUserMixin, TagsMixin, CommentsMixin, CountsMixin
):
    __tablename__ = "source"

    # Basic information
    title = Column(String, nullable=False)  # Source name or title, required
    description = Column(Text)
    content = deferred(
        Column(Text)
    )  # Raw text content from source, extracted - deferred for performance
    source_type_id = Column(
        GUID(), ForeignKey("type_lookup.id")
    )  # Type of source (e.g., 'website', 'document')

    # Status relationship
    status_id = Column(GUID(), ForeignKey("status.id"))

    # Additional information
    url = Column(String)  # Optional, URL if the source is a website
    citation = Column(Text)  # Optional, citation details for papers or books
    language_code = Column(
        String(5), comment="Language in IETF language tag format"
    )  # Language of the source (e.g., 'en-US')

    # File metadata as JSONB object
    source_metadata = Column(
        JSONB, default=dict
    )  # Should contain file_path, file_type, file_size, file_hash, original_filename

    # Relationships
    source_type = relationship("TypeLookup", back_populates="sources")
    status = relationship("Status", back_populates="sources")
    user = relationship("User", foreign_keys="[Source.user_id]", back_populates="created_sources")
    prompt_templates = relationship("PromptTemplate", back_populates="source")
    prompts = relationship("Prompt", back_populates="source")
    tests = relationship("Test", back_populates="source")
    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin=(
            "and_(Comment.entity_id == foreign(Source.id), Comment.entity_type == 'Source')"
        ),
        viewonly=True,
        uselist=True,
    )

    @hybrid_property
    def file_type(self):
        """Extract file_type from source_metadata JSONB field"""
        if self.source_metadata:
            return self.source_metadata.get("file_type")
        return None

    @file_type.expression
    def file_type(cls):
        """SQLAlchemy expression for filtering file_type"""
        return cls.source_metadata["file_type"].astext

    @hybrid_property
    def file_size(self):
        """Extract file_size from source_metadata JSONB field"""
        if self.source_metadata:
            return self.source_metadata.get("file_size")
        return None

    @file_size.expression
    def file_size(cls):
        """SQLAlchemy expression for filtering file_size"""
        return cls.source_metadata["file_size"].astext.cast(Integer)
