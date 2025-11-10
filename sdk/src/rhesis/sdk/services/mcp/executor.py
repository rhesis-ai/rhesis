"""Tool executor for MCP Agent - handles pure execution of tool calls."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.schemas import ToolCall, ToolResult

if TYPE_CHECKING:
    from rhesis.sdk.services.mcp.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executor for MCP tools with optional response filtering.

    This component handles pure execution of tool calls without any
    business logic or decision-making. It simply takes tool calls and
    returns results.
    """

    def __init__(
        self,
        mcp_client: MCPClient,
        provider_config: Optional["ProviderConfig"] = None,
    ):
        """
        Initialize the ToolExecutor.

        Args:
            mcp_client: MCP client instance for connecting to MCP servers
            provider_config: Optional provider configuration for response filtering
        """
        self.mcp_client = mcp_client
        self.provider_config = provider_config

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

            # Filter response if provider config is set
            if self.provider_config:
                result = self.provider_config.filter_response(result, tool_call.tool_name)

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
