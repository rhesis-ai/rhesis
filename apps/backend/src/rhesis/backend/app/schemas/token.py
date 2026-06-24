from datetime import datetime
from typing import ClassVar, List, Optional, Set

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


class TokenBase(Base):
    name: str
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None
    user_id: UUID4
    organization_id: Optional[UUID4] = None
    # Single-project boundary of the token. NULL = not project-restricted.
    project_id: Optional[UUID4] = None
    # SP9: optional explicit permission subset. NULL = inherit owner's full access.
    scopes: Optional[List[str]] = None


class TokenCreate(TokenBase):
    token: str
    token_hash: str
    token_obfuscated: str
    user_id: UUID4
    organization_id: Optional[UUID4] = None
    project_id: Optional[UUID4] = None


class TokenUpdate(TokenBase):
    # project_id and scopes are mint-time-only; stripped from any update payload
    # so a token's project boundary / capability set can never be widened in place.
    _IMMUTABLE_FIELDS: ClassVar[Set[str]] = {"project_id", "scopes"}

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
    scopes: Optional[List[str]] = None


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
