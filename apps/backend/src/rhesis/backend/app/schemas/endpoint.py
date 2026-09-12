from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    field_validator,
    model_serializer,
    model_validator,
)

from rhesis.backend.app.models.enums import (
    EndpointAuthType,
    EndpointConfigSource,
    EndpointConnectionType,
    EndpointEnvironment,
    EndpointResponseFormat,
)
from rhesis.backend.app.schemas.base import Base, ServerIdentity
from rhesis.backend.app.schemas.references import ProjectReference, StatusReference
from rhesis.backend.app.schemas.user import UserReference


def _check_timeout_seconds(v: int | None) -> int | None:
    if v is not None and (v < 1 or v > 3600):
        raise ValueError("timeout_seconds must be between 1 and 3600")
    return v


# --- Endpoint metadata sub-models ---
# Each allows extra keys for forward-compatibility and strips None on serialization
# so the JSON column stays clean.


class _MetadataBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_serializer(mode="wrap")
    def _exclude_none(self, handler):
        return {k: v for k, v in handler(self).items() if v is not None}


class SdkConnectionMetadata(_MetadataBase):
    project_id: Optional[str] = None
    environment: Optional[str] = None
    function_name: Optional[str] = None


class FunctionSchemaMetadata(_MetadataBase):
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    return_type: Optional[str] = None


class MappingInfoMetadata(_MetadataBase):
    source: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    generated_at: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, v: float | None) -> float | None:
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class ValidationErrorMetadata(_MetadataBase):
    error: Optional[str] = None
    timestamp: Optional[str] = None
    exception_type: Optional[str] = None
    reason: Optional[str] = None


class EndpointMetadata(_MetadataBase):
    sdk_connection: Optional[SdkConnectionMetadata] = None
    function_schema: Optional[FunctionSchemaMetadata] = None
    mapping_info: Optional[MappingInfoMetadata] = None
    validation_error: Optional[ValidationErrorMetadata] = None
    last_error: Optional[str] = None
    created_at: Optional[str] = None
    last_registered: Optional[str] = None
    timeout_seconds: Optional[int] = None

    @field_validator("timeout_seconds")
    @classmethod
    def _validate_timeout_seconds(cls, v: int | None) -> int | None:
        return _check_timeout_seconds(v)


# --- Endpoint schemas ---


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
    endpoint_metadata: Optional[EndpointMetadata] = None

    # Request Structure
    method: Optional[str] = None
    endpoint_path: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_mapping: Optional[Dict[str, Any]] = None
    input_mappings: Optional[Dict[str, Any]] = None

    # Response Handling
    response_format: EndpointResponseFormat = EndpointResponseFormat.JSON
    response_mapping: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None

    project_id: Optional[UUID4] = None  # Inferred from X-Project-Id session scope when omitted
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    # Tracing control
    disable_tracing: bool = False

    timeout_seconds: Optional[int] = None

    @field_validator("timeout_seconds")
    @classmethod
    def _validate_timeout_seconds(cls, v: int | None) -> int | None:
        return _check_timeout_seconds(v)

    auth_type: Optional[EndpointAuthType] = EndpointAuthType.BEARER_TOKEN
    auth_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_url: Optional[str] = None
    scopes: Optional[List[str]] = None
    audience: Optional[str] = None
    extra_payload: Optional[Dict[str, Any]] = None
    # last_token and last_token_expires_at are intentionally excluded:
    # they are managed internally by the OAuth token-refresh flow and must
    # not be writable by API clients.


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


class EndpointMappingTestRequest(Base):
    """Test draft mappings against a stored endpoint using its stored credentials.

    The endpoint's URL, method, headers, and auth are taken from the database.
    Only the mappings and input data are supplied by the caller.
    """

    request_mapping: Dict[str, Any]
    response_mapping: Dict[str, str]
    input_data: Dict[str, Any]
    response_format: Optional[EndpointResponseFormat] = None


class Endpoint(Base, ServerIdentity):
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
    endpoint_metadata: Optional[EndpointMetadata] = None

    # Request Structure
    method: Optional[str] = None
    endpoint_path: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_mapping: Optional[Dict[str, Any]] = None
    input_mappings: Optional[Dict[str, Any]] = None

    # Response Handling
    response_format: EndpointResponseFormat = EndpointResponseFormat.JSON
    response_mapping: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None

    project_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Tracing control
    disable_tracing: bool = False

    timeout_seconds: Optional[int] = None

    auth_type: Optional[EndpointAuthType] = None
    has_auth_token: bool = False
    # Sensitive fields excluded from response:
    # auth_token, client_secret, last_token, last_token_expires_at
    # These can be set via Create/Update but are never returned
    client_id: Optional[str] = None
    token_url: Optional[str] = None
    scopes: Optional[List[str]] = None
    audience: Optional[str] = None
    extra_payload: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def _extract_timeout_from_metadata(cls, data):
        """Pull timeout_seconds out of endpoint_metadata for dict inputs.

        ORM objects expose timeout_seconds via a @property, so Pydantic's
        from_attributes picks it up during field validation — no mutation needed.
        """
        if not isinstance(data, dict):
            return data
        meta = data.get("endpoint_metadata")
        timeout = None
        if isinstance(meta, dict) and "timeout_seconds" in meta:
            timeout = meta["timeout_seconds"]
        elif isinstance(meta, EndpointMetadata) and meta.timeout_seconds is not None:
            timeout = meta.timeout_seconds
        if timeout is not None:
            data.setdefault("timeout_seconds", timeout)
        return data


# The detailed model with expanded relations
class EndpointDetail(Endpoint):
    name: Optional[str] = None
    status: Optional[StatusReference] = None
    user: Optional[UserReference] = None
    project: Optional[ProjectReference] = None


class EndpointBulkDeleteRequest(BaseModel):
    endpoint_ids: List[UUID4]


class EndpointBulkDeleteResponse(BaseModel):
    deleted_ids: List[str]
    not_found_ids: List[str]


# Auto-configure schemas — use BaseModel (not Base) since these are
# transient DTOs that should not carry id/nano_id UUID fields.


class AutoConfigureRequest(BaseModel):
    """Request schema for AI-powered endpoint auto-configuration."""

    input_text: str  # The "paste anything" content
    url: Optional[str] = None  # Pre-filled URL
    auth_token: Optional[str] = None  # Pre-filled auth token
    method: Optional[str] = None  # Pre-filled HTTP method
    probe: bool = True  # Whether to probe the live endpoint


class AutoConfigureResult(BaseModel):
    """Result of auto-configuration — produced entirely by the LLM."""

    status: Literal["success", "partial", "failed"] = "success"
    error: Optional[str] = None
    # Generated mappings
    request_mapping: Optional[Dict[str, Any]] = None
    response_mapping: Optional[Dict[str, Any]] = None
    request_headers: Optional[Dict[str, str]] = None
    # Endpoint basics
    url: Optional[str] = None
    method: str = "POST"
    # Detection results
    conversation_mode: Literal["single_turn", "stateless", "stateful"] = "single_turn"
    # LLM-generated probe body (replaces hardcoded _build_test_body)
    probe_request: Optional[Dict[str, Any]] = None
    # Transparency
    confidence: float = 0.0
    reasoning: str = ""
    warnings: List[str] = []
    # Probe results (populated by the service, not the LLM)
    probe_response: Optional[Dict[str, Any]] = None
    probe_success: bool = False
    probe_attempts: int = 0
    probe_error: Optional[str] = None
    probe_status_code: Optional[int] = None
