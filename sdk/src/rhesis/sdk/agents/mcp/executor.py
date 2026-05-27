"""Tool executor for MCP Agent - handles pure execution of tool calls."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from opentelemetry import trace

from rhesis.sdk.agents._tool_tracing import (
    stamp_tool_exception,
    stamp_tool_result,
    tool_invoke_span,
)
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

        Emits an ``ai.tool.invoke`` span per call, nesting under whatever
        root span is active (e.g. ``function.architect_chat``).  Dynamic
        attributes (tool name, success, error, input/output preview) are
        stamped at runtime since they vary per call -- static decorator
        attributes can't express that.

        Raises:
            MCPConnectionError: If connection to MCP server fails
            MCPApplicationError: If tool returns fatal error
        """
        with tool_invoke_span(
            tool_call.tool_name,
            tool_type="mcp",
            arguments=tool_call.arguments,
            span_kind=trace.SpanKind.CLIENT,
        ) as span:
            try:
                result = await self._execute_tool_inner(tool_call)
            except MCPApplicationError as exc:
                stamp_tool_exception(span, exc, error_type="mcp_application_error")
                raise
            except (TimeoutError, ConnectionError, OSError) as exc:
                stamp_tool_exception(span, exc, error_type="mcp_connection_error")
                raise MCPConnectionError(
                    f"Failed to connect to MCP server: {exc}",
                    original_error=exc,
                ) from exc
            except RuntimeError as exc:
                error_msg = str(exc).lower()
                if "not connected" in error_msg or "connection" in error_msg:
                    stamp_tool_exception(span, exc, error_type="mcp_connection_error")
                    logger.error(f"Connection error: {exc}")
                    raise MCPConnectionError(
                        f"Connection error: {exc}",
                        original_error=exc,
                    ) from exc
                logger.warning(f"Tool {tool_call.tool_name} runtime error: {exc}")
                result = ToolResult(
                    tool_name=tool_call.tool_name,
                    success=False,
                    error=str(exc),
                )
            except Exception as exc:
                logger.warning(f"Tool {tool_call.tool_name} failed with unexpected error: {exc}")
                result = ToolResult(
                    tool_name=tool_call.tool_name,
                    success=False,
                    error=str(exc),
                )

            stamp_tool_result(span, result)
            return result

    async def _execute_tool_inner(self, tool_call: ToolCall) -> ToolResult:
        """Core MCP invocation -- returns a ToolResult or raises a
        connection/application error for the span wrapper to translate."""
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
            logger.warning(
                f"Tool {tool_call.tool_name} returned recoverable error ({status_code}): {detail}"
            )
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=f"Status {status_code}: {detail}",
            )

        logger.info(
            f"Tool {tool_call.tool_name} executed successfully, returned {len(content)} characters"
        )
        return ToolResult(
            tool_name=tool_call.tool_name,
            success=True,
            content=content,
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
