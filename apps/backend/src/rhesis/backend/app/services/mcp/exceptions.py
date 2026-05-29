"""MCP error mapping to HTTP responses."""

import logging

from fastapi import HTTPException

from rhesis.sdk.agents.mcp.exceptions import MCPApplicationError, MCPError

logger = logging.getLogger(__name__)


def handle_mcp_exception(e: Exception, operation: str) -> HTTPException:
    """
    Map MCP exceptions to HTTP responses using their status codes.

    Args:
        e: The caught exception
        operation: Description of operation (e.g., "search", "extract", "query")

    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(e, MCPError):
        # All MCP errors have status_code set by their __init__
        status_code = e.status_code if e.status_code else 500

        # For MCPApplicationError, use the detail attribute directly to avoid redundant prefixes
        # For other errors, use the string representation
        if isinstance(e, MCPApplicationError):
            message = e.detail
        else:
            message = str(e)

        # Map MCP authentication errors (401, 403) to 502 Bad Gateway
        # These are external service auth issues, not user session issues
        # This prevents the frontend from logging users out when MCP tools have auth problems
        if status_code in {401, 403} and e.category == "application":
            status_code = 502
            message = f"MCP tool authentication failed: {message}"

        # Log based on severity (client errors vs server errors)
        original_error_name = type(e.original_error).__name__ if e.original_error else None
        if status_code >= 500:
            logger.error(
                f"MCP {operation} error [{e.category}] ({status_code}): {message}",
                exc_info=True,
                extra={"category": e.category, "original_error": original_error_name},
            )
        else:
            logger.warning(
                f"MCP {operation} error [{e.category}] ({status_code}): {message}",
                extra={"category": e.category, "original_error": original_error_name},
            )

        return HTTPException(status_code=status_code, detail=message)

    # Non-MCP errors
    logger.error(f"Unexpected error in MCP {operation}: {str(e)}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=f"An unexpected error occurred during {operation}. Please try again.",
    )
