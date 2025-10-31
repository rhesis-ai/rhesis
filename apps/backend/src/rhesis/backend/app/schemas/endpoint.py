from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import UUID4

from rhesis.backend.app.models.enums import (
    EndpointAuthType,
    EndpointConfigSource,
    EndpointEnvironment,
    EndpointProtocol,
    EndpointResponseFormat,
)
from rhesis.backend.app.schemas import Base


# Endpoint schemas
class EndpointBase(Base):
    name: str
    description: Optional[str] = None
    protocol: EndpointProtocol
    url: str
    auth: Optional[Dict[str, Any]] = None
    environment: EndpointEnvironment = EndpointEnvironment.DEVELOPMENT

    # Configuration Source
    config_source: EndpointConfigSource = EndpointConfigSource.MANUAL
    openapi_spec_url: Optional[str] = None
    openapi_spec: Optional[Dict[str, Any]] = None
    llm_suggestions: Optional[Dict[str, Any]] = None

    # Request Structure
    method: Optional[str] = None
    endpoint_path: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_body_template: Optional[Dict[str, Any]] = None
    input_mappings: Optional[Dict[str, Any]] = None

    # Response Handling
    response_format: EndpointResponseFormat = EndpointResponseFormat.JSON
    response_mappings: Optional[Dict[str, str]] = None
    validation_rules: Optional[Dict[str, Any]] = None

    project_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    auth_type: Optional[EndpointAuthType] = None
    auth_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_url: Optional[str] = None
    scopes: Optional[List[str]] = None
    audience: Optional[str] = None
    extra_payload: Optional[Dict[str, Any]] = None
    last_token: Optional[str] = None
    last_token_expires_at: Optional[datetime] = None


class EndpointCreate(EndpointBase):
    pass


class EndpointUpdate(EndpointBase):
    name: Optional[str] = None
    protocol: Optional[EndpointProtocol] = None
    url: Optional[str] = None


class Endpoint(Base):
    """Response schema - excludes sensitive write-only fields"""

    id: UUID4
    name: str
    description: Optional[str] = None
    protocol: EndpointProtocol
    url: str
    auth: Optional[Dict[str, Any]] = None
    environment: EndpointEnvironment = EndpointEnvironment.DEVELOPMENT

    # Configuration Source
    config_source: EndpointConfigSource = EndpointConfigSource.MANUAL
    openapi_spec_url: Optional[str] = None
    openapi_spec: Optional[Dict[str, Any]] = None
    llm_suggestions: Optional[Dict[str, Any]] = None

    # Request Structure
    method: Optional[str] = None
    endpoint_path: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_body_template: Optional[Dict[str, Any]] = None
    input_mappings: Optional[Dict[str, Any]] = None

    # Response Handling
    response_format: EndpointResponseFormat = EndpointResponseFormat.JSON
    response_mappings: Optional[Dict[str, str]] = None
    validation_rules: Optional[Dict[str, Any]] = None

    project_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    auth_type: Optional[EndpointAuthType] = None
    # Sensitive fields excluded from response:
    # auth_token, client_secret, last_token, last_token_expires_at
    # These can be set via Create/Update but are never returned
    client_id: Optional[str] = None
    token_url: Optional[str] = None
    scopes: Optional[List[str]] = None
    audience: Optional[str] = None
    extra_payload: Optional[Dict[str, Any]] = None
