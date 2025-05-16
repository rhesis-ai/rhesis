from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# Status schemas
class StatusBase(Base):
    name: str
    description: Optional[str] = None
    entity_type_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class StatusCreate(StatusBase):
    pass


class StatusUpdate(StatusBase):
    name: Optional[str] = None


class Status(StatusBase):
    pass
