from datetime import datetime
from typing import List, Optional, Union

from pydantic import UUID4, Field

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.status import Status
from rhesis.backend.app.schemas.tag import Tag
from rhesis.backend.app.schemas.user import UserReference


# Behavior schemas
class BehaviorBase(Base):
    name: str
    description: Optional[str] = None
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class BehaviorCreate(BehaviorBase):
    pass


class BehaviorUpdate(BehaviorBase):
    name: Optional[str] = None


class Behavior(BehaviorBase):
    tags: List[Tag] = Field(default_factory=list)
    created_at: Optional[Union[datetime, str]] = None
    status: Optional[Status] = None
    user: Optional[UserReference] = None
