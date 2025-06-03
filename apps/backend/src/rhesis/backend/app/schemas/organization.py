from datetime import datetime
from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# User schemas
class OrganizationBase(Base):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = True
    max_users: Optional[int] = None
    subscription_ends_at: Optional[datetime] = None
    domain: Optional[str] = None
    is_domain_verified: Optional[bool] = False
    owner_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    is_onboarding_complete: Optional[bool] = False


class OrganizationCreate(OrganizationBase):
    pass
    # owner_id: UUID4
    # user_id: UUID4


class OrganizationUpdate(OrganizationBase):
    email: Optional[str] = None


class Organization(OrganizationBase):
    pass
