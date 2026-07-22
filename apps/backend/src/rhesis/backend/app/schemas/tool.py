import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import UUID4, ConfigDict, field_serializer

from .base import Base
from .status import Status
from .tag import TagRead
from .type_lookup import TypeLookup
from .user import User
from .user import UserReference as _BaseUserReference


class ToolBase(Base):
    """Base schema for Tool"""

    name: str
    description: Optional[str] = None
    tool_provider_type_id: UUID4
    status_id: Optional[UUID4] = None
    tool_metadata: Optional[Dict[str, Any]] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


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
    user_id: Optional[UUID4] = None

    @field_serializer("credentials")
    def serialize_credentials(self, value: Optional[Dict[str, str]]) -> Optional[str]:
        """Convert credentials dict to JSON string for storage in encrypted column"""
        if value is None:
            return None
        return json.dumps(value)


class Tool(Base):
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
    status_id: Optional[UUID4] = None
    tool_metadata: Optional[Dict[str, Any]] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None

    # Sensitive field excluded from response:
    # credentials - can be set via Create/Update but is never returned

    # Relationships
    tool_provider_type: Optional[TypeLookup] = None
    status: Optional[Status] = None
    user: Optional[User] = None

    model_config = ConfigDict(from_attributes=True)


# Lightweight reference schemas for ToolDetail's relationship fields.
# Mirrors the shape schema_factory.create_detailed_schema previously derived
# by reflection (see utils/schema_factory.py common_fields).
class StatusReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class TypeLookupReference(Base):
    id: UUID4
    description: Optional[str] = None
    type_name: Optional[str] = None
    type_value: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None
    icon: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None

    model_config = ConfigDict(from_attributes=True)


class UserReference(_BaseUserReference):
    """Extends the shared UserReference with organization_id, which the
    schema_factory-generated reference for Tool included."""

    organization_id: Optional[UUID4] = None


# The detailed model with expanded relations
class ToolDetail(Tool):
    id: UUID4
    nano_id: Optional[str]
    name: Optional[str] = None

    tool_provider_type: Optional[TypeLookupReference] = None
    status: Optional[StatusReference] = None
    user: Optional[UserReference] = None
    organization: Optional[OrganizationReference] = None
    project: Optional[ProjectReference] = None
