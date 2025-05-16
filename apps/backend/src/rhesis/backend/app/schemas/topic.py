from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# Topic schemas
class TopicBase(Base):
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID4] = None
    entity_type_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class TopicCreate(TopicBase):
    pass


class TopicUpdate(TopicBase):
    name: Optional[str] = None


class Topic(TopicBase):
    pass
