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


class MCPAuthenticationError(MCPError):
    """Raised when authentication or authorization fails."""

    pass


class MCPNotFoundError(MCPError):
    """Raised when a resource or item is not found."""

    pass


class MCPDataFormatError(MCPError):
    """Raised when data format is invalid, JSON parsing fails, or max iterations reached."""

    pass


class MCPConnectionError(MCPError):
    """Raised when connection to MCP server fails or times out."""

    pass
