from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# DemographicGroup schemas
class DemographicBase(Base):
    name: str
    description: Optional[str] = None
    dimension_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class DemographicCreate(DemographicBase):
    pass


class DemographicUpdate(DemographicBase):
    name: Optional[str] = None


class Demographic(DemographicBase):
    pass
