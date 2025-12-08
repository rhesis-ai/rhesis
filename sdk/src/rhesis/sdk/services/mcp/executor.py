"""Tool executor for MCP Agent - handles pure execution of tool calls."""

import logging
from typing import Any, Dict, List

from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.exceptions import MCPConnectionError
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
            ToolResult with success=True/False based on application layer outcome

        Raises:
            MCPConnectionError: If connection to MCP server fails (infrastructure layer)
        """
        try:
            logger.info(f"Executing tool: {tool_call.tool_name}")
            logger.debug(f"Arguments: {tool_call.arguments}")

            # Call the MCP tool with the provided arguments
            result = await self.mcp_client.call_tool(tool_call.tool_name, tool_call.arguments)

            # Check if MCP protocol indicates an error from the tool
            if hasattr(result, "isError") and result.isError:
                # Tool executed but returned an error
                content = self._extract_content(result)
                logger.warning(f"Tool {tool_call.tool_name} returned error: {content}")
                return ToolResult(
                    tool_name=tool_call.tool_name, success=False, content="", error=content
                )

            # Tool executed successfully
            content = self._extract_content(result)
            logger.info(
                f"Tool {tool_call.tool_name} executed successfully, "
                f"returned {len(content)} characters"
            )
            return ToolResult(tool_name=tool_call.tool_name, success=True, content=content)

        except (TimeoutError, ConnectionError, OSError) as e:
            # Infrastructure failures - raise immediately
            error_msg = str(e)
            logger.error(f"Connection error executing tool {tool_call.tool_name}: {error_msg}")
            raise MCPConnectionError(f"Failed to connect to MCP server: {error_msg}") from e

        except RuntimeError as e:
            # Check if it's a connection-related RuntimeError
            error_msg = str(e).lower()
            if "not connected" in error_msg or "connection" in error_msg:
                logger.error(f"Connection error: {error_msg}")
                raise MCPConnectionError(f"Connection error: {error_msg}") from e
            # Other RuntimeErrors are application errors
            logger.warning(f"Tool {tool_call.tool_name} runtime error: {str(e)}")
            return ToolResult(tool_name=tool_call.tool_name, success=False, error=str(e))

        except Exception as e:
            # All other exceptions are application-layer errors
            error_msg = str(e)
            logger.warning(f"Tool {tool_call.tool_name} failed: {error_msg}")
            return ToolResult(tool_name=tool_call.tool_name, success=False, error=error_msg)

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
