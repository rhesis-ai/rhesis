from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# Risk schemas
class RiskBase(Base):
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class RiskCreate(RiskBase):
    pass


class RiskUpdate(RiskBase):
    name: Optional[str] = None
    description: Optional[str] = None


class Risk(RiskBase):
    pass
