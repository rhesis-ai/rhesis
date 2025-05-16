from datetime import datetime
from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


class TokenBase(Base):
    name: str
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None
    user_id: UUID4
    organization_id: Optional[UUID4] = None


class TokenCreate(TokenBase):
    token: str
    token_obfuscated: str
    user_id: UUID4
    organization_id: Optional[UUID4] = None


class TokenUpdate(TokenBase):
    name: Optional[str] = None
    token: Optional[str] = None
    token_obfuscated: Optional[str] = None
    token_type: Optional[str] = None
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    last_refreshed_at: Optional[datetime] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


# For list and detail views - excludes the actual token value
class TokenRead(TokenBase):
    id: UUID4
    token_obfuscated: str
    last_used_at: Optional[datetime]
    last_refreshed_at: Optional[datetime]
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
