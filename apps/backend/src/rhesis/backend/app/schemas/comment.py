import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rhesis.backend.app.constants import EntityType

from .base import Base
from .emoji_reaction import EmojiReaction


class CommentBase(Base):
    """Base Comment schema with common fields"""

    content: str = Field(..., description="The comment content")
    emojis: Optional[Dict[str, List[EmojiReaction]]] = Field(
        default_factory=dict,
        description="Emoji reactions stored as {emoji_character: [list_of_user_reactions]}. "
        "Example: {'🚀': [{'user_id': 'uuid1', 'user_name': 'John'}], "
        "'👍': [{'user_id': 'uuid2', 'user_name': 'Jane'}]}",
    )
    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: EntityType = Field(
        ...,
        description=(
            "Type of entity: 'Test', 'TestSet', 'TestRun', 'TestResult', 'Metric', "
            "'Model', 'Prompt', 'Behavior', 'Category', 'Task', 'Source', 'Trace'"
        ),
    )


class CommentCreate(BaseModel):
    """Schema for creating a new comment"""

    content: str = Field(..., description="The comment content")

    entity_id: UUID = Field(..., description="ID of the entity this comment belongs to")
    entity_type: EntityType = Field(
        ...,
        description=(
            "Type of entity: 'Test', 'TestSet', 'TestRun', 'TestResult', 'Metric', "
            "'Model', 'Prompt', 'Behavior', 'Category', 'Task', 'Source', 'Trace'"
        ),
    )

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CommentUpdate(BaseModel):
    """Schema for updating an existing comment"""

    content: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Comment(CommentBase):
    """Full Comment schema with all fields"""

    id: UUID
    user_id: UUID
    organization_id: Optional[UUID] = None
    created_at: Union[datetime.datetime, str]
    updated_at: Union[datetime.datetime, str]

    model_config = ConfigDict(from_attributes=True)
