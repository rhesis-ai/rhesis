from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, ConfigDict

from rhesis.backend.app.auth.capabilities import ResourceType

from .affordances import WithPermittedActions
from .base import Base
from .status import Status
from .tag import TagRead
from .type_lookup import TypeLookup
from .user import User
from .user import UserReference as _BaseUserReference


class TaskBase(BaseModel):
    """Base schema for Task without auto-generated fields"""

    title: str
    description: Optional[str] = None
    assignee_id: Optional[UUID4] = None
    status_id: UUID4
    priority_id: Optional[UUID4] = None
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    task_metadata: Optional[Dict] = None


class TaskCreate(BaseModel):
    """Schema for creating a new Task - user_id is auto-populated from authenticated user"""

    title: str
    description: Optional[str] = None
    assignee_id: Optional[UUID4] = None
    status_id: UUID4
    priority_id: Optional[UUID4] = None
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    task_metadata: Optional[Dict] = None


class TaskUpdate(BaseModel):
    """Schema for updating a Task"""

    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    priority_id: Optional[UUID4] = None
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    task_metadata: Optional[Dict] = None


class Task(Base, WithPermittedActions):
    """Schema for Task with relationships and auto-generated fields.

    ``permitted_actions`` (server-resolved object-level affordances) is filled
    automatically during response serialization — see
    :class:`WithPermittedActions`.

    Edit (update) is permitted for the creator (``:own``) or the assignee
    (``:assigned``); delete is permitted for the creator only (``:own``).
    """

    __resource_type__ = ResourceType.TASK
    __assignee_attr__ = "assignee_id"

    title: str
    description: Optional[str] = None
    user_id: UUID4  # Creator/owner of the task (from OrganizationAndUserMixin)
    assignee_id: Optional[UUID4] = None
    status_id: UUID4
    priority_id: Optional[UUID4] = None
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    task_metadata: Optional[Dict] = None
    comment_count: Optional[int] = 0

    # User relationships
    user: Optional[User] = None  # Creator/owner (from OrganizationAndUserMixin)
    assignee: Optional[User] = None

    # Status and priority
    status: Optional[Status] = None
    priority: Optional[TypeLookup] = None

    # Entity relationships
    # comment_id is now stored in task_metadata

    model_config = ConfigDict(from_attributes=True)


# Lightweight reference schemas for TaskDetail's relationship fields.
# Mirrors the shape schema_factory.create_detailed_schema previously derived
# by reflection (see utils/schema_factory.py common_fields).
class StatusReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class TypeLookupReference(Base):
    id: UUID4
    description: Optional[str] = None
    type_name: Optional[str] = None
    type_value: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

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


class OrganizationReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None

    model_config = ConfigDict(from_attributes=True)


class UserReference(_BaseUserReference):
    """Extends the shared UserReference with organization_id, which the
    schema_factory-generated reference for Task included."""

    organization_id: Optional[UUID4] = None


# The detailed model with expanded relations
class TaskDetail(Task):
    id: UUID4
    nano_id: Optional[str]
    title: Optional[str] = None
    user_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None

    user: Optional[UserReference] = None
    assignee: Optional[UserReference] = None
    status: Optional[StatusReference] = None
    priority: Optional[TypeLookupReference] = None
    project: Optional[ProjectReference] = None
    organization: Optional[OrganizationReference] = None
