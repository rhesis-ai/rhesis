from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# Category schemas
class TypeLookupBase(Base):
    type_name: str
    type_value: str
    description: Optional[str] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class TypeLookupCreate(TypeLookupBase):
    pass


class TypeLookupUpdate(TypeLookupBase):
    type_name: Optional[str] = None
    type_value: Optional[str] = None


class TypeLookup(TypeLookupBase):
    pass
