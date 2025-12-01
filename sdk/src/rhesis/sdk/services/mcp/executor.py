"""Tool executor for MCP Agent - handles pure execution of tool calls."""

import logging
from typing import Any, Dict, List

from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.exceptions import (
    MCPAuthenticationError,
    MCPConnectionError,
)
from rhesis.sdk.services.mcp.schemas import ToolCall, ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Handles execution of MCP tool calls.

    Separates pure tool execution from agent logic.
    """

    def __init__(self, mcp_client: MCPClient):
        """
        Initialize the executor.

        Args:
            mcp_client: Connected MCP client for calling tools
        """
        self.mcp_client = mcp_client

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools from the MCP server.

        Returns:
            List of tool dictionaries with name, description, and input schema
        """
        return await self.mcp_client.list_tools()

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool and return its result.

        Args:
            tool_call: Specifies which tool to call and with what arguments

        Returns:
            ToolResult containing output content or error details

        Raises:
            MCPAuthenticationError: If authentication fails
            MCPConnectionError: If connection fails
        """
        try:
            logger.info(f"Executing tool: {tool_call.tool_name}")
            logger.debug(f"Arguments: {tool_call.arguments}")

            # Call the MCP tool with the provided arguments
            result = await self.mcp_client.call_tool(tool_call.tool_name, tool_call.arguments)

            # Extract content from the result
            content = self._extract_content(result)

            logger.info(
                f"Tool {tool_call.tool_name} executed successfully, "
                f"returned {len(content)} characters"
            )

            return ToolResult(tool_name=tool_call.tool_name, success=True, content=content)

        except (TimeoutError, ConnectionError, OSError) as e:
            # Connection errors - raise immediately
            error_msg = str(e)
            logger.error(f"Connection error executing tool {tool_call.tool_name}: {error_msg}")
            raise MCPConnectionError(f"Failed to connect to MCP server: {error_msg}") from e

        except RuntimeError as e:
            # Check if it's a connection-related RuntimeError
            error_msg = str(e).lower()
            if self._is_connection_error(error_msg):
                logger.error(f"Connection error: {error_msg}")
                raise MCPConnectionError(f"Connection error: {error_msg}") from e
            # Otherwise, treat as other error (fall through)

        except Exception as e:
            # Check for authentication errors in the message
            if self._is_authentication_error(str(e)):
                logger.error(f"Authentication error executing tool {tool_call.tool_name}: {str(e)}")
                raise MCPAuthenticationError(f"Authentication failed: {str(e)}") from e

            # All other errors - return ToolResult for agent to handle
            error_msg = str(e)
            logger.error(f"Tool {tool_call.tool_name} failed: {error_msg}")
            return ToolResult(
                tool_name=tool_call.tool_name, success=False, content="", error=error_msg
            )

    def _extract_content(self, result) -> str:
        """
        Extract text content from MCP tool result.

        Returns raw content without formatting - formatting is handled at agent level.

        Args:
            result: Result from MCP tool call

        Returns:
            Extracted text content (raw, unformatted)
        """
        content_parts = []
        content_list = getattr(result, "content", None)

        if not content_list:
            return ""

        for content_item in content_list:
            if hasattr(content_item, "text"):
                content_parts.append(content_item.text)

        return "\n\n".join(content_parts)

    def _is_authentication_error(self, error_msg: str) -> bool:
        """
        Check if error message indicates an authentication error.

        Args:
            error_msg: Error message to check

        Returns:
            True if error is authentication-related
        """
        error_lower = error_msg.lower()
        auth_keywords = [
            "unauthorized",
            "invalid api key",
            "authentication",
            "not authenticated",
            "401",
            "403",
            "forbidden",
        ]
        return any(keyword in error_lower for keyword in auth_keywords)

    def _is_connection_error(self, error_msg: str) -> bool:
        """
        Check if error message indicates a connection error.

        Args:
            error_msg: Error message to check

        Returns:
            True if error is connection-related
        """
        connection_keywords = [
            "not connected",
            "connection",
            "timeout",
            "connection refused",
            "network",
        ]
        return any(keyword in error_msg for keyword in connection_keywords)
