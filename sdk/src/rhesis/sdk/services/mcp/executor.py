"""Tool executor for MCP Agent - handles pure execution of tool calls."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.exceptions import MCPApplicationError, MCPConnectionError
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
            MCPApplicationError: If tool returns fatal error (5xx, 401, 403)
                - 404 and other 4xx errors are treated as recoverable
        """
        try:
            logger.info(f"Executing tool: {tool_call.tool_name}")
            logger.info(f"Arguments: {tool_call.arguments}")

            # Call the MCP tool with the provided arguments
            result = await self.mcp_client.call_tool(tool_call.tool_name, tool_call.arguments)

            # Extract content first (needed for both success and error paths)
            content = self._extract_content(result)

            # Check if MCP protocol indicates an error from the tool (transport layer)
            if hasattr(result, "isError") and result.isError:
                logger.warning(f"Tool {tool_call.tool_name} returned transport error: {content}")
                return ToolResult(
                    tool_name=tool_call.tool_name, success=False, content="", error=content
                )

            # Check for application-layer errors
            error_info = self._parse_application_error(content)
            if error_info:
                status_code, detail = error_info

                # Classify: fatal vs recoverable
                # Fatal errors interrupt the agent immediately - auth issues or server errors
                is_fatal = status_code in {401, 403} or status_code >= 500

                if is_fatal:
                    # Agent cannot recover - raise immediately
                    logger.warning(
                        f"Tool {tool_call.tool_name} returned fatal error ({status_code}): {detail}"
                    )
                    raise MCPApplicationError(status_code=status_code, detail=detail)
                else:
                    # Agent can handle (retry, try different tool, etc.)
                    # Return as tool failure, let agent decide next step
                    logger.warning(
                        f"Tool {tool_call.tool_name} returned recoverable error "
                        f"({status_code}): {detail}"
                    )
                    return ToolResult(
                        tool_name=tool_call.tool_name,
                        success=False,
                        error=f"Status {status_code}: {detail}",
                    )

            # Tool executed successfully at both transport and application layers
            logger.info(
                f"Tool {tool_call.tool_name} executed successfully, "
                f"returned {len(content)} characters"
            )
            return ToolResult(tool_name=tool_call.tool_name, success=True, content=content)

        except MCPApplicationError:
            # Fatal errors propagate immediately
            raise

        except (TimeoutError, ConnectionError, OSError) as e:
            # Infrastructure failures - raise immediately
            error_msg = str(e)
            logger.error(f"Connection error executing tool {tool_call.tool_name}: {error_msg}")
            raise MCPConnectionError(
                f"Failed to connect to MCP server: {error_msg}", original_error=e
            ) from e

        except RuntimeError as e:
            # Check if it's a connection-related RuntimeError
            error_msg = str(e).lower()
            if "not connected" in error_msg or "connection" in error_msg:
                logger.error(f"Connection error: {error_msg}")
                raise MCPConnectionError(f"Connection error: {str(e)}", original_error=e) from e
            # Other RuntimeErrors are application-level failures - let agent retry or handle
            logger.warning(f"Tool {tool_call.tool_name} runtime error: {str(e)}")
            return ToolResult(tool_name=tool_call.tool_name, success=False, error=str(e))

        except Exception as e:
            # Unexpected errors - let agent retry or handle
            error_msg = str(e)
            logger.warning(f"Tool {tool_call.tool_name} failed with unexpected error: {error_msg}")
            return ToolResult(tool_name=tool_call.tool_name, success=False, error=error_msg)

    def _parse_application_error(self, content: str) -> Optional[Tuple[int, str]]:
        """
        Parse application error from content and extract status code.

        Only parses JSON responses with a status field >= 400.

        Args:
            content: The text content from the MCP tool result

        Returns:
            Tuple of (status_code, detail) if error found, None otherwise
        """
        if not content:
            return None

        # Try parsing as JSON first
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                # Check for status field with error code
                status = data.get("status") or data.get("status_code")
                if status and isinstance(status, int) and status >= 400:
                    # Extract error message from common fields
                    message = (
                        data.get("message") or data.get("detail") or data.get("error") or str(data)
                    )

                    logger.warning(f"Parsed JSON error: status={status}, message={message}")
                    return (status, message)
        except json.JSONDecodeError:
            # Not valid JSON - let it pass through as normal content
            pass

        # No status code found - let it pass through as normal content
        # The LLM can reason about any errors in the content itself
        return None

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
            # Try to extract text content directly
            if hasattr(content_item, "text"):
                content_parts.append(content_item.text)
            # If content is wrapped in a resource, extract text from the resource
            elif hasattr(content_item, "resource"):
                resource = content_item.resource
                if hasattr(resource, "text"):
                    content_parts.append(resource.text)
                else:
                    logger.warning(f"Resource found but no text attribute: {type(resource)}")

        return "\n\n".join(content_parts)
