from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import UUID4, ConfigDict

from rhesis.backend.app.schemas.base import Base, ServerIdentity
from rhesis.backend.app.schemas.tag import Tag
from rhesis.backend.app.schemas.type_lookup import TypeLookup
from rhesis.backend.app.schemas.user import User


# Source Types Enum - Defines available source types with corresponding handlers
class SourceType(str, Enum):
    DOCUMENT = "Document"
    WEBSITE = "Website"
    DATABASE = "Database"
    CODE = "Code"
    MANUAL = "Manual"
    TOOL = "Tool"

    @classmethod
    def get_value(cls, source_type):
        """Get the string value of a source type"""
        if isinstance(source_type, cls):
            return source_type.value
        return source_type

    @classmethod
    def get_all_values(cls):
        """Get all source type values as a list"""
        return [source_type.value for source_type in cls]


# Base schema for Source (without content for performance)
class SourceBase(Base):
    title: str  # Source name is required
    description: Optional[str] = None  # Description is optional
    # content is intentionally excluded from base schema - use SourceWithContent to access it
    source_type_id: Optional[UUID4] = None  # Type of source (e.g., website, paper, etc.)
    source_metadata: Optional[Dict[str, Any]] = None  # File metadata as JSON object
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


# Schema for creating a new Source
class SourceCreate(SourceBase):
    content: Optional[str] = None  # Raw text content from source, extracted (only for create)


# Schema for updating an existing Source (all fields are optional)
class SourceUpdate(SourceBase):
    title: Optional[str] = None  # Make title optional for updates
    content: Optional[str] = None  # Raw text content from source, extracted (only for update)


# Schema for returning a Source (content field is deferred in the model for performance)
class Source(SourceBase, ServerIdentity):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    tags: Optional[List[Tag]] = []
    counts: Optional[Dict[str, int]] = None  # Comment and task counts from CountsMixin
    # Related objects
    source_type: Optional[TypeLookup] = None
    user: Optional[User] = None

    model_config = ConfigDict(from_attributes=True)


# Schema for returning a Source WITH content (use /sources/{id}/detail endpoint)
class SourceWithContent(Source):
    content: Optional[str] = None  # Raw text content from source, extracted

    model_config = ConfigDict(from_attributes=True)
