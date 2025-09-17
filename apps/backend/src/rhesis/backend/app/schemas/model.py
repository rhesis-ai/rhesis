from typing import Dict, List, Optional

from pydantic import UUID4

from .base import Base
from .status import Status
from .tag import Tag
from .type_lookup import TypeLookup
from .user import User


class ModelBase(Base):
    """Base schema for Model"""

    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    model_name: str
    endpoint: str
    key: str
    request_headers: Optional[Dict] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class ModelCreate(ModelBase):
    """Schema for creating a new Model"""

    provider_type_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None


class ModelUpdate(ModelBase):
    """Schema for updating an existing Model"""

    name: Optional[str] = None
    model_name: Optional[str] = None
    endpoint: Optional[str] = None
    key: Optional[str] = None
    provider_type_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None


class Model(ModelBase):
    """Complete Model schema with relationships"""

    id: UUID4
    provider_type_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    provider_type: Optional[TypeLookup] = None
    status: Optional[Status] = None
    owner: Optional[User] = None
    assignee: Optional[User] = None
    tags: Optional[List[Tag]] = []

    class Config:
        from_attributes = True
