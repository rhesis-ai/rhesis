import re
from datetime import datetime
from typing import Optional

from pydantic import UUID4, field_validator

from rhesis.backend.app.schemas import Base

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


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
    slug: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        if not v:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError(
                "Slug must be 3-50 characters, lowercase alphanumeric "
                "and hyphens, starting and ending with a letter or digit"
            )
        if "--" in v:
            raise ValueError("Slug must not contain consecutive hyphens")
        return v


class OrganizationCreate(OrganizationBase):
    pass
    # owner_id: UUID4
    # user_id: UUID4


class OrganizationUpdate(OrganizationBase):
    name: Optional[str] = None  # Make name optional for updates
    email: Optional[str] = None


class Organization(OrganizationBase):
    pass
