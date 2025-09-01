import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from rhesis.backend.app.constants import EntityType

from .base import Base
from .emoji_reaction import EmojiReaction


class CommentBase(Base):
    """Base Comment schema with common fields"""

    content: str = Field(..., description="The comment content")
    emojis: Optional[Dict[str, List[EmojiReaction]]] = Field(
        default_factory=dict, description="Emoji reactions with user details"
    )
    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: EntityType = Field(
        ...,
        description="Type of entity: 'Test', 'TestSet', 'TestRun', 'Metric', 'Model', 'Prompt', 'Behavior', 'Category'",
    )


class CommentCreate(BaseModel):
    """Schema for creating a new comment"""

    content: str = Field(..., description="The comment content")

    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: EntityType = Field(
        ...,
        description="Type of entity: 'Test', 'TestSet', 'TestRun', 'Metric', 'Model', 'Prompt', 'Behavior', 'Category'",
    )

    class Config:
        from_attributes = True


class CommentUpdate(BaseModel):
    """Schema for updating an existing comment"""

    content: Optional[str] = None

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
