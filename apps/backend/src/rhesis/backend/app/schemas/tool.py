import json
from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import UUID4, ConfigDict, field_serializer

from rhesis.backend.app.schemas.base import Base, ServerIdentity

from .references import TypeLookupReference
from .type_lookup import TypeLookup


class ToolBase(Base):
    """Base schema for Tool"""

    name: str
    description: Optional[str] = None
    tool_provider_type_id: UUID4
    tool_metadata: Optional[Dict[str, Any]] = None


class ToolCreate(ToolBase):
    """Schema for creating a new Tool"""

    # Required - JSON dict of credentials, will be encrypted in DB
    # Examples: {"NOTION_TOKEN": "ntn_abc..."} or
    credentials: Dict[str, str]
    tool_metadata: Optional[Dict[str, Any]] = (
        None  # Optional - can be empty for provider-based MCP tools
    )

    @field_serializer("credentials")
    def serialize_credentials(self, value: Dict[str, str]) -> str:
        """Convert credentials dict to JSON string for storage in encrypted column"""
        return json.dumps(value)


class ToolUpdate(ToolBase):
    """Schema for updating an existing Tool"""

    name: Optional[str] = None
    tool_provider_type_id: Optional[UUID4] = None
    # Optional - only update if provided, will be re-encrypted
    credentials: Optional[Dict[str, str]] = None

    @field_serializer("credentials")
    def serialize_credentials(self, value: Optional[Dict[str, str]]) -> Optional[str]:
        """Convert credentials dict to JSON string for storage in encrypted column"""
        if value is None:
            return None
        return json.dumps(value)


class Tool(Base, ServerIdentity):
    """
    Complete Tool schema with relationships.

    Note: credentials is excluded from response for security.
    It can be set via Create/Update but is never returned.

    Tools can be owned by both organizations and users.
    """

    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    name: str
    description: Optional[str] = None
    tool_provider_type_id: UUID4
    tool_metadata: Optional[Dict[str, Any]] = None

    # Sensitive field excluded from response:
    # credentials - can be set via Create/Update but is never returned

    # Relationships
    tool_provider_type: Optional[TypeLookup] = None

    model_config = ConfigDict(from_attributes=True)


# Extends ToolBase, not Tool -- Tool declares status/user as full relationship
# objects, which would leak back in through inheritance if this extended it instead.
class ToolDetail(ToolBase, ServerIdentity):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    name: Optional[str] = None

    tool_provider_type: Optional[TypeLookupReference] = None

    model_config = ConfigDict(from_attributes=True)
