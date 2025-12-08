"""Custom exceptions for MCP service errors."""


class MCPError(Exception):
    """Base exception for all MCP-related errors."""

    def __init__(self, message: str, original_error: Exception = None):
        """
        Initialize MCP error.

        Args:
            message: Error message
            original_error: Original exception that caused this error (optional)
        """
        super().__init__(message)
        self.original_error = original_error


# ============================================================================
# Client Errors (4xx) - User can fix these
# ============================================================================


class MCPClientError(MCPError):
    """
    Base class for client-side errors.

    These errors indicate issues with configuration or how the SDK is being used.
    User can fix these by updating configuration or correcting API usage.
    """

    pass


class MCPConfigurationError(MCPClientError):
    """
    Tool configuration is invalid or incomplete.

    Raised when:
        - Tool not found in database
        - Tool is not configured as MCP type
        - Credentials are missing or invalid format
        - Required configuration fields not set

    Maps to HTTP 404 (Not Found) in backend.
    """

    pass


class MCPValidationError(MCPClientError):
    """
    Input validation failed - SDK was called incorrectly.

    Raised when:
        - Invalid parameter types passed to SDK methods
        - Schema validation failed
        - Required fields missing in SDK call
        - Max iterations reached (agent configuration issue)
        - LLM response parsing failed

    Maps to HTTP 422 (Unprocessable Entity) in backend.
    """

    pass


# ============================================================================
# Server Errors (5xx) - Infrastructure/transient issues
# ============================================================================


class MCPServerError(MCPError):
    """
    Base class for server-side errors.

    These errors indicate infrastructure or network issues that may be transient.
    """

    pass


class MCPConnectionError(MCPServerError):
    """
    Cannot establish or maintain connection to MCP server.

    Raised when:
        - Network timeout
        - Connection refused
        - Server not reachable
        - MCP server process not running
        - Session disconnected

    Maps to HTTP 503 (Service Unavailable) in backend.
    """

    pass
