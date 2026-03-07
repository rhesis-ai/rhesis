"""Local tool provider for in-process agent execution.

Provides the same tool interface as the SDK's MCPTool but dispatches
calls directly to the FastAPI app via ASGI transport, skipping the
MCP protocol layer entirely. Used by the Celery worker when running
the ArchitectAgent inside the backend process.

Auth is handled via a delegation token passed as a Bearer header,
so tenant isolation is preserved without requiring a static API key.
"""

import json
import logging
from typing import Any, Dict, List

import httpx

from rhesis.sdk.agents.base import MCPTool
from rhesis.sdk.agents.schemas import ToolResult

from .tools import build_tools_and_operations

logger = logging.getLogger(__name__)


class LocalToolProvider(MCPTool):
    """In-process tool provider that calls FastAPI routes via ASGI.

    Subclasses MCPTool so the BaseAgent isinstance checks recognise it
    in get_available_tools() and execute_tool(). No real MCP client is
    needed — tool definitions come from mcp_tools.yaml and dispatch
    goes straight through httpx ASGITransport.
    """

    def __init__(self, fastapi_app: Any, auth_token: str):
        # Skip MCPTool.__init__ — we don't have an MCP client.
        self._app = fastapi_app
        self._auth_header = f"Bearer {auth_token}"
        self._tool_defs: List[Dict[str, Any]] = []
        self._operation_map: Dict[str, dict] = {}
        self._initialized = False
        self._connected = True  # MCPTool attribute; always "connected"

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            mcp_tools, self._operation_map = build_tools_and_operations(self._app)
            self._tool_defs = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema,
                }
                for t in mcp_tools
            ]
            self._initialized = True

    async def _ensure_connected(self) -> None:
        """No-op — always connected (in-process)."""

    async def connect(self) -> None:
        """No-op — no transport to connect."""

    async def disconnect(self) -> None:
        """No-op — no transport to disconnect."""

    async def list_tools(self) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        return self._tool_defs

    async def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        self._ensure_initialized()

        op = self._operation_map.get(tool_name)
        if op is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

        arguments = dict(kwargs)
        headers = {"Authorization": self._auth_header}

        # Path params
        path = op["path"]
        for param in op["parameters"]:
            if param.get("in") == "path" and param["name"] in arguments:
                path = path.replace(
                    f"{{{param['name']}}}",
                    str(arguments.pop(param["name"])),
                )

        # Query params
        query: Dict[str, Any] = {}
        for param in op["parameters"]:
            if param.get("in") == "query" and param["name"] in arguments:
                query[param["name"]] = arguments.pop(param["name"])

        # Remaining arguments = request body
        body = arguments if arguments else None

        try:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url="http://internal") as client:
                response = await client.request(
                    method=op["method"],
                    url=path,
                    headers=headers,
                    params=query,
                    json=body,
                )

            if response.status_code >= 400:
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=json.dumps(
                        {
                            "status_code": response.status_code,
                            "detail": detail,
                        },
                        default=str,
                    ),
                )

            try:
                data = response.json()
            except Exception:
                data = response.text
            return ToolResult(
                tool_name=tool_name,
                success=True,
                content=json.dumps(data, default=str),
            )

        except Exception as e:
            logger.error("Local tool execution failed: %s", e, exc_info=True)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )
