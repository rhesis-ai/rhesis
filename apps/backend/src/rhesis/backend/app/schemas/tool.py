from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import UUID4, ConfigDict

from .base import Base
from .status import Status
from .type_lookup import TypeLookup


class ToolBase(Base):
    """Base schema for Tool"""

    name: str
    description: Optional[str] = None
    tool_type_id: UUID4
    tool_provider_id: UUID4
    status_id: Optional[UUID4] = None
    tool_metadata: Optional[Dict[str, Any]] = None
    organization_id: Optional[UUID4] = None


class ToolCreate(ToolBase):
    """Schema for creating a new Tool"""

    auth_token: str  # Required - will be encrypted in DB
    tool_metadata: Dict[str, Any]  # Required - JSON with {{auth_token}} placeholder for MCP config


class ToolUpdate(ToolBase):
    """Schema for updating an existing Tool"""

    name: Optional[str] = None
    tool_type_id: Optional[UUID4] = None
    tool_provider_id: Optional[UUID4] = None
    auth_token: Optional[str] = None  # Optional - only update if provided, will be re-encrypted


class Tool(Base):
    """
    Complete Tool schema with relationships.

    Note: auth_token is excluded from response for security.
    It can be set via Create/Update but is never returned.

    Tools are organization-level resources (not user-owned).
    """

    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    name: str
    description: Optional[str] = None
    tool_type_id: UUID4
    tool_provider_id: UUID4
    status_id: Optional[UUID4] = None
    tool_metadata: Dict[str, Any]
    organization_id: Optional[UUID4] = None

    # Sensitive field excluded from response:
    # auth_token - can be set via Create/Update but is never returned

    # Relationships
    tool_type: Optional[TypeLookup] = None
    tool_provider: Optional[TypeLookup] = None
    status: Optional[Status] = None

    model_config = ConfigDict(from_attributes=True)
