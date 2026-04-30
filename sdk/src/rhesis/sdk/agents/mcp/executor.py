"""Tool executor for MCP Agent - handles pure execution of tool calls."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from rhesis.sdk.agents.base import extract_mcp_content
from rhesis.sdk.agents.mcp.client import MCPClient
from rhesis.sdk.agents.mcp.exceptions import (
    MCPApplicationError,
    MCPConnectionError,
)
from rhesis.sdk.agents.schemas import ToolCall, ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Handles execution of MCP tool calls.

    Separates pure tool execution from agent logic.
    """

    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from the MCP server."""
        return await self.mcp_client.list_tools()

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool and return its result.

        Raises:
            MCPConnectionError: If connection to MCP server fails
            MCPApplicationError: If tool returns fatal error
        """
        try:
            logger.info(f"Executing tool: {tool_call.tool_name}")
            logger.info(f"Arguments: {tool_call.arguments}")

            result = await self.mcp_client.call_tool(tool_call.tool_name, tool_call.arguments)
            content = self._extract_content(result)

            if hasattr(result, "isError") and result.isError:
                logger.warning(f"Tool {tool_call.tool_name} returned transport error: {content}")
                return ToolResult(
                    tool_name=tool_call.tool_name,
                    success=False,
                    content="",
                    error=content,
                )

            error_info = self._parse_application_error(content)
            if error_info:
                status_code, detail = error_info
                is_fatal = status_code in {401, 403} or status_code >= 500
                if is_fatal:
                    logger.warning(
                        f"Tool {tool_call.tool_name} returned fatal error ({status_code}): {detail}"
                    )
                    raise MCPApplicationError(status_code=status_code, detail=detail)
                else:
                    logger.warning(
                        f"Tool {tool_call.tool_name} returned "
                        f"recoverable error "
                        f"({status_code}): {detail}"
                    )
                    return ToolResult(
                        tool_name=tool_call.tool_name,
                        success=False,
                        error=f"Status {status_code}: {detail}",
                    )

            logger.info(
                f"Tool {tool_call.tool_name} executed "
                f"successfully, returned {len(content)} characters"
            )
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=True,
                content=content,
            )

        except MCPApplicationError:
            raise

        except (TimeoutError, ConnectionError, OSError) as e:
            error_msg = str(e)
            logger.error(f"Connection error executing tool {tool_call.tool_name}: {error_msg}")
            raise MCPConnectionError(
                f"Failed to connect to MCP server: {error_msg}",
                original_error=e,
            ) from e

        except RuntimeError as e:
            error_msg = str(e).lower()
            if "not connected" in error_msg or "connection" in error_msg:
                logger.error(f"Connection error: {error_msg}")
                raise MCPConnectionError(
                    f"Connection error: {str(e)}",
                    original_error=e,
                ) from e
            logger.warning(f"Tool {tool_call.tool_name} runtime error: {str(e)}")
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=str(e),
            )

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Tool {tool_call.tool_name} failed with unexpected error: {error_msg}")
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=error_msg,
            )

    def _parse_application_error(self, content: str) -> Optional[Tuple[int, str]]:
        """Parse application error from content."""
        if not content:
            return None
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                status = data.get("status") or data.get("status_code")
                if status and isinstance(status, int) and status >= 400:
                    message = (
                        data.get("message") or data.get("detail") or data.get("error") or str(data)
                    )
                    logger.warning(f"Parsed JSON error: status={status}, message={message}")
                    return (status, message)
        except json.JSONDecodeError:
            pass
        return None

    def _extract_content(self, result) -> str:
        """Extract text content from MCP tool result."""
        return extract_mcp_content(result)
