from datetime import datetime
from typing import Dict, Optional

from pydantic import UUID4, BaseModel

from .base import Base
from .status import Status
from .type_lookup import TypeLookup
from .user import User


class TaskBase(BaseModel):
    """Base schema for Task without auto-generated fields"""

    title: str
    description: Optional[str] = None
    creator_id: UUID4
    assignee_id: Optional[UUID4] = None
    status_id: UUID4
    priority_id: Optional[UUID4] = None
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    task_metadata: Optional[Dict] = None


class TaskCreate(BaseModel):
    """Schema for creating a new Task - creator_id is auto-populated from authenticated user"""

    title: str
    description: Optional[str] = None
    creator_id: Optional[UUID4] = None  # Auto-populated from current user
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


class Task(Base):
    """Schema for Task with relationships and auto-generated fields"""

    title: str
    description: Optional[str] = None
    creator_id: UUID4
    assignee_id: Optional[UUID4] = None
    status_id: UUID4
    priority_id: Optional[UUID4] = None
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    task_metadata: Optional[Dict] = None
    total_comments: Optional[int] = 0

    # User relationships
    creator: Optional[User] = None
    assignee: Optional[User] = None

    # Status and priority
    status: Optional[Status] = None
    priority: Optional[TypeLookup] = None

    # Entity relationships
    # comment_id is now stored in task_metadata

    class Config:
        from_attributes = True
