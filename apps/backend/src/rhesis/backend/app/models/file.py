from sqlalchemy import Column, Integer, String, Text

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin, ProjectMixin


class File(Base, ProjectMixin, OrganizationAndUserMixin):
    __tablename__ = "file"

    # File metadata
    filename = Column(String(255), nullable=False)
    content_type = Column(String(127), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)

    # Polymorphic entity reference
    entity_id = Column(GUID(), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)

    # Ordering for multiple files on same entity
    position = Column(Integer, nullable=False, default=0)

    # Object-storage path (relative to the active backend root).
    storage_path = Column(String(512), nullable=True)

    # SHA-256 hex digest of the original file bytes.
    content_hash = Column(String(64), nullable=True)

    # Text extracted from the file at upload time (OCR / text-layer).
    extracted_text = Column(Text, nullable=True)

    # Extraction lifecycle: pending | done | failed | not_applicable
    extraction_status = Column(String(16), nullable=False, server_default="pending")
