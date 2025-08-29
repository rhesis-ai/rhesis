from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from rhesis.backend.app.constants import CommentEntityType

from .base import Base


class CommentBase(Base):
    """Base Comment schema with common fields"""

    comment_text: str = Field(..., description="The comment text content")
    emojis: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Emoji reactions")
    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: CommentEntityType = Field(
        ...,
        description="Type of entity: 'test', 'test_set', 'test_run', 'metric', 'model', 'prompt', 'behavior', 'category'",
    )


class CommentCreate(BaseModel):
    """Schema for creating a new comment"""

    comment_text: str = Field(..., description="The comment text content")
    emojis: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Emoji reactions")
    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: CommentEntityType = Field(
        ...,
        description="Type of entity: 'test', 'test_set', 'test_run', 'metric', 'model', 'prompt', 'behavior', 'category'",
    )


class CommentUpdate(BaseModel):
    """Schema for updating an existing comment"""

    comment_text: Optional[str] = Field(None, description="The comment text content")
    emojis: Optional[Dict[str, Any]] = Field(None, description="Emoji reactions")


class Comment(CommentBase):
    """Full Comment schema with all fields"""

    id: UUID
    user_id: UUID
    organization_id: Optional[UUID] = None

    class Config:
        from_attributes = True
