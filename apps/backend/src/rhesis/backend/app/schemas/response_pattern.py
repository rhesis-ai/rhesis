from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# ResponsePattern schemas
class ResponsePatternBase(Base):
    text: str
    behavior_id: int
    reponse_type: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class ResponsePatternCreate(ResponsePatternBase):
    pass


class ResponsePatternUpdate(ResponsePatternBase):
    text: Optional[str] = None
    behavior_id: Optional[int] = None


class ResponsePattern(ResponsePatternBase):
    pass
