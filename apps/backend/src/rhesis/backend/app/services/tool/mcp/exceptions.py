"""MCP error mapping to HTTP responses."""

import logging

from fastapi import HTTPException

from rhesis.backend.app.error_handlers import UpstreamHTTPException
from rhesis.sdk.agents.mcp.exceptions import MCPApplicationError, MCPError

logger = logging.getLogger(__name__)


def _already_logged(exc: HTTPException) -> HTTPException:
    """Mark an exception this function has logged, so the global handler won't repeat it."""
    exc.rhesis_logged = True
    return exc


def handle_mcp_exception(e: Exception, operation: str) -> HTTPException:
    """
    Map MCP exceptions to HTTP responses using their status codes.

    Args:
        e: The caught exception
        operation: Description of operation (e.g., "search", "extract", "query")

    Returns:
        HTTPException with appropriate status code and message. Rejected
        credentials and connection failures come back as an
        ``UpstreamHTTPException``, so the reason survives 5xx masking: those
        describe the user's own MCP server, which is the one thing they can act
        on. Everything else is masked by the global handler.
    """
    if isinstance(e, MCPError):
        # All MCP errors have status_code set by their __init__
        status_code = e.status_code if e.status_code else 500

        # MCPApplicationError.detail is the MCP server's own response text, so it
        # is the user's to read. Every other message was written by our own code.
        upstream_detail = e.detail if isinstance(e, MCPApplicationError) else None
        message = upstream_detail if upstream_detail is not None else str(e)

        # A tool's 401/403 is its own token being rejected, not the caller's
        # Rhesis session: answering 401 here makes the frontend log them out.
        tool_auth_failed = status_code in {401, 403} and e.category == "application"
        if tool_auth_failed:
            status_code = 502
            message = (
                f"MCP tool authentication failed: {upstream_detail}"
                if upstream_detail
                else "MCP tool authentication failed."
            )

        # Rejected credentials or an unreachable server describe the user's own
        # MCP setup; nothing of ours is in either message.
        from_users_mcp_server = tool_auth_failed or e.category == "connection"

        # Log based on severity (client errors vs server errors)
        original_error_name = type(e.original_error).__name__ if e.original_error else None
        if status_code >= 500 and not from_users_mcp_server:
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

        exception_class = UpstreamHTTPException if from_users_mcp_server else HTTPException
        return _already_logged(exception_class(status_code=status_code, detail=message))

    # Non-MCP errors
    logger.error(f"Unexpected error in MCP {operation}: {str(e)}", exc_info=True)
    return _already_logged(
        HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during {operation}. Please try again.",
        )
    )
