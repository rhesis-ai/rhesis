"""Tool executor for MCP Agent - handles pure execution of tool calls."""

import json
import logging
from typing import Any, Dict, List

from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.schemas import ToolCall, ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Stateless executor for MCP tools.

    This component handles pure execution of tool calls without any
    business logic or decision-making. It simply takes tool calls and
    returns results.
    """

    def __init__(self, mcp_client: MCPClient):
        """
        Initialize the ToolExecutor.

        Args:
            mcp_client: MCP client instance for connecting to MCP servers
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
        Execute a single tool call.

        Args:
            tool_call: ToolCall instance with tool_name and arguments

        Returns:
            ToolResult with success status, content, or error message
        """
        try:
            logger.info(f"Executing tool: {tool_call.tool_name}")
            logger.debug(f"Arguments: {tool_call.arguments}")

            # Call the MCP tool
            # Ensure arguments is a dict
            args = tool_call.arguments if isinstance(tool_call.arguments, dict) else {}

            result = await self.mcp_client.call_tool(tool_call.tool_name, args)

            # Extract content from the result
            content = self._extract_content(result)

            logger.info(
                f"Tool {tool_call.tool_name} executed successfully, "
                f"returned {len(content)} characters"
            )

            return ToolResult(tool_name=tool_call.tool_name, success=True, content=content)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Tool {tool_call.tool_name} failed: {error_msg}")

            return ToolResult(
                tool_name=tool_call.tool_name, success=False, content="", error=error_msg
            )

    def _extract_content(self, result) -> str:
        """
        Extract text content from MCP tool result.

        Args:
            result: Result from MCP tool call

        Returns:
            Extracted text content
        """
        content_parts = []
        content_list = getattr(result, "content", None)

        if not content_list:
            return ""

        for content_item in content_list:
            if hasattr(content_item, "text"):
                try:
                    # Try to parse as JSON first for structured data
                    data = json.loads(content_item.text)
                    # Convert structured data to readable text
                    content_parts.append(self._format_json_content(data))
                except json.JSONDecodeError:
                    # If not JSON, use as plain text
                    content_parts.append(content_item.text)

        return "\n\n".join(content_parts)

    def _format_json_content(self, data: Dict[str, Any]) -> str:
        """
        Format JSON data into readable text.

        Args:
            data: JSON data structure

        Returns:
            Formatted text representation
        """
        # For large/complex JSON, return formatted JSON string
        # This ensures all data is preserved and readable
        if isinstance(data, dict):
            # Check if it's a simple dict that can be formatted nicely
            if len(data) <= 10 and not any(isinstance(v, (dict, list)) for v in data.values()):
                parts = []
                for key, value in data.items():
                    parts.append(f"{key}: {value}")
                return "\n".join(parts)

        # For complex structures, return formatted JSON
        return json.dumps(data, indent=2)
