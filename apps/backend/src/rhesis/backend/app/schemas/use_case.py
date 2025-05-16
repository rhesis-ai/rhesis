from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# UseCase schemas
class UseCaseBase(Base):
    name: str
    description: str
    industry: Optional[str] = None
    application: Optional[str] = None
    is_active: Optional[bool] = True
    status_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class UseCaseCreate(UseCaseBase):
    pass


class UseCaseUpdate(UseCaseBase):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class UseCase(UseCaseBase):
    pass
