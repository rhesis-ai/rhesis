from typing import Dict, Optional

from pydantic import UUID4, ConfigDict

from .base import Base
from .status import Status
from .type_lookup import TypeLookup


class ToolBase(Base):
    """Base schema for Tool"""

    name: str
    description: Optional[str] = None
    organization_id: Optional[UUID4] = None


class ToolCreate(ToolBase):
    """Schema for creating a new Tool"""

    tool_type_id: UUID4
    tool_provider_id: UUID4
    status_id: UUID4
    auth_token: str  # Will be encrypted in DB
    tool_metadata: Dict  # JSON with {{auth_token}} placeholder


class ToolUpdate(ToolBase):
    """Schema for updating an existing Tool"""

    name: Optional[str] = None
    description: Optional[str] = None
    tool_type_id: Optional[UUID4] = None
    tool_provider_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    auth_token: Optional[str] = None  # Optional - only update if provided
    tool_metadata: Optional[Dict] = None


class Tool(ToolBase):
    """Complete Tool schema with relationships"""

    id: UUID4
    tool_type_id: UUID4
    tool_provider_id: UUID4
    status_id: UUID4
    tool_metadata: Dict
    tool_type: Optional[TypeLookup] = None
    tool_provider: Optional[TypeLookup] = None
    status: Optional[Status] = None
    # Note: auth_token NOT included in response for security

    model_config = ConfigDict(from_attributes=True)
