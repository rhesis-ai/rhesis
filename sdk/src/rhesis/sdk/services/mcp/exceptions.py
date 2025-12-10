"""Custom exceptions for MCP service errors."""

from typing import Literal, Optional


class MCPError(Exception):
    """
    Base exception for all MCP-related errors.

    Attributes:
        category: Error category for programmatic routing
        status_code: HTTP status code if applicable (for application errors)
        original_error: Original exception that caused this error
    """

    def __init__(
        self,
        message: str,
        category: Literal["connection", "config", "validation", "application"],
        status_code: Optional[int] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize MCP error.

        Args:
            message: Error message
            category: Error category for routing
            status_code: HTTP status code if applicable
            original_error: Original exception that caused this error (optional)
        """
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.original_error = original_error


class MCPConfigurationError(MCPError):
    """
    Tool configuration is invalid or incomplete.

    Raised when:
        - Tool not found in database
        - Tool is not configured as MCP type
        - Credentials are missing or invalid format
        - Required configuration fields not set

    Maps to HTTP 404 (Not Found) in backend.
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """
        Initialize configuration error.

        Args:
            message: Error message
            original_error: Original exception that caused this error (optional)
        """
        super().__init__(message, category="config", status_code=404, original_error=original_error)


class MCPValidationError(MCPError):
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

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """
        Initialize validation error.

        Args:
            message: Error message
            original_error: Original exception that caused this error (optional)
        """
        super().__init__(
            message, category="validation", status_code=422, original_error=original_error
        )


class MCPApplicationError(MCPError):
    """
    Application-level error from MCP tool (HTTP 4xx/5xx from external API).

    Raised when:
        - External API returns 401 Unauthorized
        - External API returns 404 Not Found
        - External API returns 403 Forbidden
        - External API returns any 4xx/5xx status

    Attributes:
        status_code: HTTP status code from the application error
        detail: Error message/details from the API
    """

    def __init__(self, status_code: int, detail: str, original_error: Optional[Exception] = None):
        """
        Initialize application error.

        Args:
            status_code: HTTP status code from the application error
            detail: Error message/details from the API
            original_error: Original exception that caused this error (optional)
        """
        self.detail = detail
        super().__init__(
            f"Application error {status_code}: {detail}",
            category="application",
            status_code=status_code,
            original_error=original_error,
        )


class MCPConnectionError(MCPError):
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

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """
        Initialize connection error.

        Args:
            message: Error message
            original_error: Original exception that caused this error (optional)
        """
        super().__init__(
            message, category="connection", status_code=503, original_error=original_error
        )
