from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import UUID4, ConfigDict, field_validator

from rhesis.backend.app.models.enums import (
    EndpointAuthType,
    EndpointConfigSource,
    EndpointConnectionType,
    EndpointEnvironment,
    EndpointResponseFormat,
)
from rhesis.backend.app.schemas import Base


# Endpoint metadata schemas
class SDKConnectionInfo(Base):
    """Information about the SDK connection for this endpoint."""

    project_id: str
    environment: str
    function_name: str


class FunctionSchemaInfo(Base):
    """Schema information for the SDK function."""

    parameters: Dict[str, Any]
    return_type: str
    description: Optional[str] = None


class EndpointMetadataSchema(Base):
    """
    Schema for endpoint_metadata JSONB field.

    Notes on mapping fields:
    - parameter_mapping: Maps function parameters to backend fields (like request_mapping)
      Example: {"location": "{{ input }}", "unit": "celsius"}
    - output_mapping: Maps function output to backend fields (like response_mapping)
      Example: {"temperature": "result.temp", "conditions": "result.weather[0].description"}
    """

    # SDK-specific fields
    sdk_connection: Optional[SDKConnectionInfo] = None
    function_schema: Optional[FunctionSchemaInfo] = None

    # SDK function mappings (for future use with invocations)
    parameter_mapping: Optional[Dict[str, Any]] = None
    output_mapping: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: Optional[str] = None
    last_registered: Optional[str] = None
    last_connected_at: Optional[str] = None

    # Legacy/other fields (for backwards compatibility)
    created_via: Optional[str] = None
    functions: Optional[List[Dict[str, Any]]] = None  # Deprecated

    model_config = ConfigDict(extra="allow")  # Allow additional fields for extensibility


# Endpoint schemas
class EndpointBase(Base):
    name: str
    description: Optional[str] = None
    connection_type: EndpointConnectionType
    url: Optional[str] = None
    auth: Optional[Dict[str, Any]] = None
    environment: EndpointEnvironment = EndpointEnvironment.DEVELOPMENT

    # Configuration Source
    config_source: EndpointConfigSource = EndpointConfigSource.MANUAL
    openapi_spec_url: Optional[str] = None
    openapi_spec: Optional[Dict[str, Any]] = None
    llm_suggestions: Optional[Dict[str, Any]] = None
    endpoint_metadata: Optional[Dict[str, Any]] = None

    # Request Structure
    method: Optional[str] = None
    endpoint_path: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_mapping: Optional[Dict[str, Any]] = None
    input_mappings: Optional[Dict[str, Any]] = None

    # Response Handling
    response_format: EndpointResponseFormat = EndpointResponseFormat.JSON
    response_mapping: Optional[Dict[str, str]] = None
    validation_rules: Optional[Dict[str, Any]] = None

    project_id: UUID4  # Required field
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    auth_type: Optional[EndpointAuthType] = EndpointAuthType.BEARER_TOKEN
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
    connection_type: Optional[EndpointConnectionType] = None
    url: Optional[str] = None
    project_id: Optional[UUID4] = None  # Optional for updates


class EndpointTestRequest(Base):
    """
    Schema for testing endpoint configurations without saving to database.

    Currently only supports REST endpoints with BEARER_TOKEN authentication.
    """

    # Required fields
    connection_type: EndpointConnectionType
    url: str
    method: str
    request_headers: Dict[str, str]
    request_mapping: Dict[str, Any]
    response_mapping: Dict[str, str]
    auth_type: EndpointAuthType
    auth_token: str
    input_data: Dict[str, Any]

    # Optional fields
    endpoint_path: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    response_format: EndpointResponseFormat = EndpointResponseFormat.JSON

    @field_validator("connection_type")
    @classmethod
    def validate_connection_type(cls, v):
        """Validate that connection_type is REST (initial implementation constraint)."""
        if v != EndpointConnectionType.REST:
            raise ValueError(f"Only REST endpoints are supported for testing. Got: {v.value}")
        return v

    @field_validator("auth_type")
    @classmethod
    def validate_auth_type(cls, v):
        """Validate that auth_type is BEARER_TOKEN (initial implementation constraint)."""
        if v != EndpointAuthType.BEARER_TOKEN:
            raise ValueError(
                f"Only BEARER_TOKEN authentication is supported for testing. Got: {v.value}"
            )
        return v

    @field_validator("input_data")
    @classmethod
    def validate_input_data(cls, v):
        """Validate that input_data contains the required 'input' field."""
        if not isinstance(v, dict):
            raise ValueError("input_data must be a dictionary")
        if "input" not in v:
            raise ValueError("input_data must contain an 'input' field")
        return v


class Endpoint(Base):
    """Response schema - excludes sensitive write-only fields"""

    id: UUID4
    name: str
    description: Optional[str] = None
    connection_type: EndpointConnectionType
    url: Optional[str] = None
    auth: Optional[Dict[str, Any]] = None
    environment: EndpointEnvironment = EndpointEnvironment.DEVELOPMENT

    # Configuration Source
    config_source: EndpointConfigSource = EndpointConfigSource.MANUAL
    openapi_spec_url: Optional[str] = None
    openapi_spec: Optional[Dict[str, Any]] = None
    llm_suggestions: Optional[Dict[str, Any]] = None
    endpoint_metadata: Optional[Dict[str, Any]] = None

    # Request Structure
    method: Optional[str] = None
    endpoint_path: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_mapping: Optional[Dict[str, Any]] = None
    input_mappings: Optional[Dict[str, Any]] = None

    # Response Handling
    response_format: EndpointResponseFormat = EndpointResponseFormat.JSON
    response_mapping: Optional[Dict[str, str]] = None
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
