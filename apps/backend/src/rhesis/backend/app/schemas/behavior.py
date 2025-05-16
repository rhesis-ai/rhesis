from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


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
    pass
