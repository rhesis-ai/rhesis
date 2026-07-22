import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.constants import EntityType

from .affordances import WithPermittedActions
from .base import Base
from .emoji_reaction import EmojiReaction
from .tag import TagRead
from .user import UserReference as _BaseUserReference


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


class Comment(CommentBase, WithPermittedActions):
    """Full Comment schema with all fields.

    ``permitted_actions`` (server-resolved object-level affordances) is filled
    automatically during response serialization — see
    :class:`WithPermittedActions`.
    """

    __resource_type__ = ResourceType.COMMENT

    id: UUID
    user_id: UUID
    organization_id: Optional[UUID] = None
    created_at: Union[datetime.datetime, str]
    updated_at: Union[datetime.datetime, str]

    model_config = ConfigDict(from_attributes=True)


# Lightweight reference schemas for CommentDetail's relationship fields.
# Mirrors the shape schema_factory.create_detailed_schema previously derived
# by reflection (see utils/schema_factory.py common_fields).
class OrganizationReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None
    icon: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserReference(_BaseUserReference):
    """Extends the shared UserReference with organization_id, which the
    schema_factory-generated reference for Comment included."""

    organization_id: Optional[UUID4] = None


# The detailed model with expanded relations
class CommentDetail(Comment):
    nano_id: Optional[str]
    content: Optional[str] = None
    user_id: Optional[UUID4] = None
    user: Optional[UserReference] = None
    organization: Optional[OrganizationReference] = None
    project: Optional[ProjectReference] = None
