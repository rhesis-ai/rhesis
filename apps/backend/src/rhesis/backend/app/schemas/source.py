from typing import Optional

from pydantic import UUID4, field_validator

from rhesis.backend.app.schemas import Base


# Base schema for Source
class SourceBase(Base):
    title: str  # Source name is required
    description: Optional[str] = None  # Description is optional
    entity_type: Optional[str] = None  # Type of source (e.g., website, paper, etc.)
    url: Optional[str] = None  # Optional URL as string with basic validation
    citation: Optional[str] = None  # Optional citation for papers or books
    language_code: Optional[str] = None  # Optional language code (BCP 47 format)
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Basic URL validation - only validate if URL is provided"""
        if v is not None and v.strip():
            # Basic URL validation - must start with http:// or https:// and have more content
            if not (v.startswith('http://') or v.startswith('https://')):
                raise ValueError('URL must start with http:// or https://')
            # Must have content after the protocol
            if v in ['http://', 'https://']:
                raise ValueError('URL must have content after the protocol')
            # Reject javascript: URLs for security
            if v.startswith('javascript:'):
                raise ValueError('JavaScript URLs are not allowed')
        return v


# Schema for creating a new Source
class SourceCreate(SourceBase):
    pass


# Schema for updating an existing Source (all fields are optional)
class SourceUpdate(SourceBase):
    title: Optional[str] = None  # Make title optional for updates


# Schema for returning a Source (typically includes an ID)
class Source(SourceBase):
    pass
