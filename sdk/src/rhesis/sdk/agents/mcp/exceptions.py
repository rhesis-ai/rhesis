"""Custom exceptions for MCP service errors."""

from typing import Literal, Optional


class MCPError(Exception):
    """Base exception for all MCP-related errors.

    Attributes:
        category: Error category for programmatic routing
        status_code: HTTP status code if applicable
        original_error: Original exception that caused this error
    """

    def __init__(
        self,
        message: str,
        category: Literal["connection", "config", "validation", "application"],
        status_code: Optional[int] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.original_error = original_error


class MCPConfigurationError(MCPError):
    """Tool configuration is invalid or incomplete."""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            category="config",
            status_code=404,
            original_error=original_error,
        )


class MCPValidationError(MCPError):
    """Input validation failed."""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            category="validation",
            status_code=422,
            original_error=original_error,
        )


class MCPApplicationError(MCPError):
    """Application-level error from MCP tool (HTTP 4xx/5xx)."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        original_error: Optional[Exception] = None,
    ):
        self.detail = detail
        super().__init__(
            f"Application error {status_code}: {detail}",
            category="application",
            status_code=status_code,
            original_error=original_error,
        )


class MCPConnectionError(MCPError):
    """Cannot establish or maintain connection to MCP server."""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            category="connection",
            status_code=503,
            original_error=original_error,
        )
