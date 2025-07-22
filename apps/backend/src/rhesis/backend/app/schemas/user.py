from typing import Optional

from pydantic import UUID4, field_validator, Field

from rhesis.backend.app.schemas import Base


# User schemas
class UserBase(Base):
    email: str = Field(..., min_length=1, description="Email address cannot be empty")
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    auth0_id: Optional[str] = None
    picture: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    organization_id: Optional[UUID4] = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Email address cannot be empty or whitespace-only')
        return v.strip()


class UserCreate(UserBase):
    send_invite: Optional[bool] = False


class UserUpdate(UserBase):
    email: Optional[str] = None


class User(UserBase):
    pass


# For use in responses where we need minimal user info
class UserReference(Base):
    id: UUID4
    given_name: Optional[str] = ""  # Default to empty string to avoid validation errors
    family_name: Optional[str] = ""  # Default to empty string to avoid validation errors
    email: Optional[str] = ""  # Default to empty string to avoid validation errors
    picture: Optional[str] = ""  # Default to empty string to avoid validation errors

    class Config:
        from_attributes = True
