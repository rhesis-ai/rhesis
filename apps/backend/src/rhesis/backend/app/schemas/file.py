from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict

from .base import Base


class FileEntityType(str, Enum):
    TEST = "Test"
    TEST_RESULT = "TestResult"
    TRACE = "Trace"
    ARCHITECT_SESSION = "ArchitectSession"


class FileResponse(Base):
    """File metadata response — never includes raw content or storage_path."""

    filename: str
    content_type: str
    size_bytes: int
    description: Optional[str] = None
    entity_id: UUID4
    entity_type: str
    position: int = 0
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    created_at: Optional[Union[datetime, str]] = None
    updated_at: Optional[Union[datetime, str]] = None
    # New fields (nullable for backward compat with un-migrated rows)
    content_hash: Optional[str] = None
    extracted_text: Optional[str] = None
    extraction_status: Optional[str] = None


class FileCreate(BaseModel):
    """Internal schema for creating file records (metadata only — no bytes)."""

    filename: str
    content_type: str
    size_bytes: int
    description: Optional[str] = None
    entity_id: UUID4
    entity_type: Union[FileEntityType, str]
    position: int = 0
    storage_path: Optional[str] = None
    content_hash: Optional[str] = None
    extraction_status: str = "pending"

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class FileUpdate(BaseModel):
    """Schema for updating file metadata."""

    description: Optional[str] = None
    position: Optional[int] = None
    storage_path: Optional[str] = None
    content_hash: Optional[str] = None
    extracted_text: Optional[str] = None
    extraction_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
