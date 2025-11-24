"""Pydantic schemas for invoker responses."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RequestDetails(BaseModel):
    """Request details for debugging and logging."""

    connection_type: str = Field(..., description="Type of connection (REST, WebSocket, SDK)")
    method: Optional[str] = Field(None, description="HTTP method or operation type")
    url: Optional[str] = Field(None, description="Request URL or URI")
    headers: Optional[Dict[str, Any]] = Field(None, description="Sanitized request headers")
    body: Optional[Any] = Field(None, description="Request body or message data")

    # SDK-specific fields
    project_id: Optional[str] = Field(None, description="SDK project ID")
    environment: Optional[str] = Field(None, description="SDK environment")
    function_name: Optional[str] = Field(None, description="SDK function name")


class ErrorResponse(BaseModel):
    """Standardized error response schema."""

    # Core error fields
    output: str = Field(..., description="User-facing error message")
    error: bool = Field(True, description="Always True for error responses")
    error_type: str = Field(..., description="Type of error (e.g., 'network_error', 'http_error')")
    message: str = Field(..., description="Technical error message for debugging")

    # Optional debugging information
    request: Optional[RequestDetails] = Field(None, description="Request details for debugging")

    # HTTP-specific fields
    status_code: Optional[int] = Field(None, description="HTTP status code")
    reason: Optional[str] = Field(None, description="HTTP reason phrase")
    response_headers: Optional[Dict[str, Any]] = Field(None, description="HTTP response headers")
    response_content: Optional[str] = Field(None, description="HTTP response content")
    response_body: Optional[str] = Field(None, description="HTTP response body")

    # Performance fields
    duration_ms: Optional[float] = Field(None, description="Operation duration in milliseconds")

    # WebSocket-specific fields
    uri: Optional[str] = Field(None, description="WebSocket URI")

    # Additional context (for extensibility)
    context: Optional[Dict[str, Any]] = Field(None, description="Additional error context")

    class Config:
        """Pydantic configuration."""

        extra = "allow"  # Allow additional fields for backward compatibility
        json_encoders = {
            # Custom encoders if needed
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.dict(exclude_none=True)


class SuccessResponse(BaseModel):
    """Standardized success response schema."""

    output: Optional[Any] = Field(None, description="Main response output")
    error: bool = Field(False, description="Always False for success responses")
    status: str = Field("completed", description="Response status")

    # Optional fields that may be present
    conversation_id: Optional[str] = Field(None, description="Conversation tracking ID")
    session_id: Optional[str] = Field(None, description="Session tracking ID")
    thread_id: Optional[str] = Field(None, description="Thread tracking ID")
    chat_id: Optional[str] = Field(None, description="Chat tracking ID")

    # Performance fields
    duration_ms: Optional[float] = Field(None, description="Operation duration in milliseconds")

    class Config:
        """Pydantic configuration."""

        extra = "allow"  # Allow additional fields for flexibility
