from sqlalchemy import Column, DateTime, Integer, String, Text

from .base import Base
from .mixins import OrganizationAndUserMixin, TagsMixin


class Source(Base, OrganizationAndUserMixin, TagsMixin):
    __tablename__ = "source"

    # Basic information
    title = Column(String, nullable=False)  # Source name or title, required
    description = Column(Text)  # Optional description of the source
    entity_type = Column(String)  # Type of entity (e.g., 'website', 'document')

    # Source location
    url = Column(String)  # Optional, URL if the source is a website
    file_path = Column(String)  # Optional, path to the source file (cloud or local)

    # File metadata
    file_type = Column(String)  # Optional, type of the source file (e.g., 'pdf', 'txt', 'docx')
    file_size = Column(Integer)
    file_hash = Column(String)
    uploaded_at = Column(DateTime)

    # Content processing
    extracted_content = Column(Text)
