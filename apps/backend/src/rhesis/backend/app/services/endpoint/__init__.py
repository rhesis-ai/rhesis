"""
Endpoint service module - manages endpoint invocation and SDK synchronization.

Public API:
-----------
Main Functions (recommended for external use):
    - invoke() - Invoke an endpoint with input data
    - get_schema() - Get endpoint schema definition
    - sync_sdk_endpoints() - Sync SDK-connected endpoints

Classes & Instances:
    - EndpointService - Main service class
    - endpoint_service - Pre-configured singleton instance

Internal Modules (not part of public API):
    - service - Core EndpointService implementation
    - sdk_sync - SDK synchronization logic
    - mapper - Mapping service integration
    - validation - Endpoint validation logic
    - cli - Command-line interface
"""

from typing import Any, Dict

from sqlalchemy.orm import Session

from .sdk_sync import sync_sdk_endpoints
from .service import EndpointService

# ==================== Singleton Instance ====================
# Pre-configured service instance for convenience
endpoint_service = EndpointService()


# ==================== User-Facing Functions ====================


async def invoke(
    db: Session,
    endpoint_id: str,
    input_data: Dict[str, Any],
    organization_id: str = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    Invoke an endpoint with input data (recommended entry point).

    This is the primary function for invoking endpoints. It handles:
    - Security filtering by organization
    - Input mapping via templates
    - Response mapping
    - Error handling

    Args:
        db: Database session
        endpoint_id: ID of the endpoint to invoke
        input_data: Input data containing:
            - input: (required) Main user input/query
            - conversation_id: (optional) Conversation tracking ID
            - context: (optional) Additional context
            - metadata: (optional) Request metadata
            - tool_calls: (optional) Available tool calls
            - **any custom fields**: Additional fields are passed through and
              available in request_mapping templates
        organization_id: Organization ID for security filtering (CRITICAL)
        user_id: User ID for context injection (CRITICAL)

    Returns:
        Dict containing the mapped response with standard fields:
            - output: Main response text
            - conversation_id: Conversation identifier
            - metadata: Response metadata
            - (other endpoint-specific fields)

    Raises:
        HTTPException: If endpoint not found or invocation fails

    Example:
        >>> result = await invoke(
        ...     db=db,
        ...     endpoint_id="endpoint-uuid",
        ...     input_data={"input": "Hello", "conversation_id": "conv-123"},
        ...     organization_id="org-uuid",
        ...     user_id="user-uuid"
        ... )
        >>> print(result["output"])
    """
    return await endpoint_service.invoke_endpoint(
        db, endpoint_id, input_data, organization_id=organization_id, user_id=user_id
    )


def get_schema() -> Dict[str, Any]:
    """
    Get the endpoint schema definition.

    Returns the JSON schema describing the expected input and output
    format for endpoints.

    Returns:
        Dict containing:
            - input_schema: Expected input structure
            - output_schema: Expected output structure

    Example:
        >>> schema = get_schema()
        >>> print(schema["input_schema"])
    """
    return endpoint_service.get_schema()


# ==================== Public API Exports ====================
# Only these symbols are part of the public API

__all__ = [
    # Primary functions (recommended)
    "invoke",
    "get_schema",
    "sync_sdk_endpoints",
    # Service class & instance (for advanced use)
    "EndpointService",
    "endpoint_service",
]
