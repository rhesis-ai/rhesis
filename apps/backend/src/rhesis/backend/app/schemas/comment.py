import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from rhesis.backend.app.constants import CommentEntityType

from .base import Base
from .emoji_reaction import EmojiReaction


class CommentBase(Base):
    """Base Comment schema with common fields"""

    comment_text: str = Field(..., description="The comment text content")
    emojis: Optional[Dict[str, List[EmojiReaction]]] = Field(
        default_factory=dict, description="Emoji reactions with user details"
    )
    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: CommentEntityType = Field(
        ...,
        description="Type of entity: 'test', 'test_set', 'test_run', 'metric', 'model', 'prompt', 'behavior', 'category'",
    )


class CommentCreate(BaseModel):
    """Schema for creating a new comment"""

    comment_text: str = Field(..., description="The comment text content")

    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: CommentEntityType = Field(
        ...,
        description="Type of entity: 'test', 'test_set', 'test_run', 'metric', 'model', 'prompt', 'behavior', 'category'",
    )

    class Config:
        from_attributes = True


class CommentUpdate(BaseModel):
    """Schema for updating an existing comment"""

    comment_text: Optional[str] = Field(None, description="The comment text content")
    # emojis field removed - emojis are managed through separate emoji endpoints

    class Config:
        from_attributes = True


class Comment(CommentBase):
    """Full Comment schema with all fields"""

    id: UUID
    user_id: UUID
    organization_id: Optional[UUID] = None
    created_at: Union[datetime.datetime, str]
    updated_at: Union[datetime.datetime, str]

    class Config:
        from_attributes = True
