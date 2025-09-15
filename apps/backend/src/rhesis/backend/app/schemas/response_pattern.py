from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# ResponsePattern schemas
class ResponsePatternBase(Base):
    text: str
    behavior_id: UUID4
    response_pattern_type_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class ResponsePatternCreate(ResponsePatternBase):
    pass


class ResponsePatternUpdate(ResponsePatternBase):
    text: Optional[str] = None
    behavior_id: Optional[UUID4] = None


class ResponsePattern(ResponsePatternBase):
    pass
