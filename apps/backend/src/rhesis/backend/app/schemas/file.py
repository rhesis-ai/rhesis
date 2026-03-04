from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict

from .base import Base


class FileEntityType(str, Enum):
    TEST = "Test"
    TEST_RESULT = "TestResult"
    TRACE = "Trace"


class FileResponse(Base):
    """File metadata response - never includes content."""

    filename: str
    content_type: str
    size_bytes: int
    description: Optional[str] = None
    entity_id: UUID4
    entity_type: FileEntityType
    position: int = 0
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    created_at: Optional[Union[datetime, str]] = None
    updated_at: Optional[Union[datetime, str]] = None


class FileCreate(BaseModel):
    """Internal schema for creating file records."""

    filename: str
    content_type: str
    size_bytes: int
    content: bytes
    description: Optional[str] = None
    entity_id: UUID4
    entity_type: FileEntityType
    position: int = 0

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class FileUpdate(BaseModel):
    """Schema for updating file metadata."""

    description: Optional[str] = None
    position: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
