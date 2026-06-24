from datetime import datetime
from typing import ClassVar, Optional, Set

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


class TokenBase(Base):
    name: str
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None
    user_id: UUID4
    organization_id: Optional[UUID4] = None
    project_id: Optional[UUID4] = None


class TokenCreate(TokenBase):
    token: str
    token_hash: str
    token_obfuscated: str
    user_id: UUID4
    organization_id: Optional[UUID4] = None
    project_id: Optional[UUID4] = None


class TokenUpdate(TokenBase):
    _IMMUTABLE_FIELDS: ClassVar[Set[str]] = {"project_id"}

    name: Optional[str] = None
    token: Optional[str] = None
    token_hash: Optional[str] = None
    token_obfuscated: Optional[str] = None
    token_type: Optional[str] = None
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    last_refreshed_at: Optional[datetime] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    def model_dump(self, **kwargs) -> dict:
        data = super().model_dump(**kwargs)
        for field in self._IMMUTABLE_FIELDS:
            data.pop(field, None)
        return data


# For list and detail views - excludes the actual token value
class TokenRead(TokenBase):
    id: UUID4
    token_obfuscated: Optional[str] = None
    last_used_at: Optional[datetime] = None
    last_refreshed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class Token(TokenBase):
    id: UUID4
    token: str
    token_obfuscated: str
    last_used_at: Optional[datetime]
    last_refreshed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# Special response schema for token creation that includes the actual token value
class TokenCreateResponse(Base):
    id: UUID4  # Add ID field for consistency
    access_token: str
    token_obfuscated: str
    token_type: str
    expires_at: Optional[datetime]
    name: str
    project_id: Optional[UUID4] = None
    last_refreshed_at: Optional[datetime] = None  # For refresh operations
