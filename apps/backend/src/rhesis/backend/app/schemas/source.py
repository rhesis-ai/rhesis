from typing import Optional

from pydantic import UUID4, HttpUrl

from rhesis.backend.app.schemas import Base


# Base schema for Source
class SourceBase(Base):
    title: str  # Source name is required
    description: Optional[str] = None  # Description is optional
    entity_type: Optional[str] = None  # Type of source (e.g., website, paper, etc.)
    url: Optional[HttpUrl] = None  # Optional, must be a valid URL
    citation: Optional[str] = None  # Optional citation for papers or books
    language_code: Optional[str] = None  # Optional language code (BCP 47 format)
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


# Schema for creating a new Source
class SourceCreate(SourceBase):
    pass


# Schema for updating an existing Source (all fields are optional)
class SourceUpdate(SourceBase):
    name: Optional[str] = None


# Schema for returning a Source (typically includes an ID)
class Source(SourceBase):
    pass
