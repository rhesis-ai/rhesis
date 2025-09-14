from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# Dimension schemas
class DimensionBase(Base):
    name: str
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class DimensionCreate(DimensionBase):
    pass


class DimensionUpdate(DimensionBase):
    name: Optional[str] = None


class Dimension(DimensionBase):
    name: Optional[str] = None  # Allow None names in response to match database reality
