"""Local tool provider for in-process agent execution.

Provides the same tool interface as the SDK's MCPTool but dispatches
calls directly to the FastAPI app via ASGI transport, skipping the
MCP protocol layer entirely. Used by the Celery worker when running
the ArchitectAgent inside the backend process.

Auth is handled via a delegation token passed as a Bearer header,
so tenant isolation is preserved without requiring a static API key.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from rhesis.sdk.agents.base import MCPTool
from rhesis.sdk.agents.constants import ToolMeta
from rhesis.sdk.agents.schemas import ToolResult

from .tools import (
    apply_query_overrides,
    build_tools_and_operations,
    format_list_response,
    load_tool_configs,
)

logger = logging.getLogger(__name__)

# One retry is enough for the blips this is aimed at. More would stall the
# turn behind a genuinely broken dependency.
_TRANSIENT_RETRIES = 1
_RETRY_DELAY_SECONDS = 0.5


class LocalToolProvider(MCPTool):
    """In-process tool provider that calls FastAPI routes via ASGI.

    Subclasses MCPTool so the BaseAgent isinstance checks recognise it
    in get_available_tools() and execute_tool(). No real MCP client is
    needed — tool definitions come from mcp_tools.yaml and dispatch
    goes straight through httpx ASGITransport.
    """

    def __init__(
        self,
        fastapi_app: Any,
        auth_token: str,
        project_id: str | None = None,
    ):
        # Skip MCPTool.__init__ — we don't have an MCP client.
        self._app = fastapi_app
        self._auth_header = f"Bearer {auth_token}"
        self._project_id = project_id
        self._tool_defs: List[Dict[str, Any]] = []
        self._operation_map: Dict[str, dict] = {}
        self._confirmation_map: Dict[str, bool] = {}
        self._initialized = False
        self._connected = True  # MCPTool attribute; always "connected"

    def _confirmation_metadata(self, tool_name: str) -> Dict[str, Any]:
        """Return ``requires_confirmation`` metadata if set in YAML."""
        if tool_name in self._confirmation_map:
            return {ToolMeta.REQUIRES_CONFIRMATION: self._confirmation_map[tool_name]}
        return {}

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            mcp_tools, self._operation_map = build_tools_and_operations(self._app)
            self._confirmation_map = {
                tc["name"]: tc[ToolMeta.REQUIRES_CONFIRMATION]
                for tc in load_tool_configs()
                if ToolMeta.REQUIRES_CONFIRMATION in tc
            }
            self._tool_defs = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema,
                    ToolMeta.HTTP_METHOD: self._operation_map.get(t.name, {}).get("method", "GET"),
                    **self._confirmation_metadata(t.name),
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
            raise ValueError(f"Tool not found: {tool_name}")

        arguments = dict(kwargs)
        headers = {"Authorization": self._auth_header}
        if self._project_id:
            headers["X-Project-Id"] = self._project_id

        # Path params
        path = op["path"]
        for param in op["parameters"]:
            if param.get("in") == "path" and param["name"] in arguments:
                path = path.replace(
                    f"{{{param['name']}}}",
                    str(arguments.pop(param["name"])),
                )

        # Query params (agent sees sanitized names, e.g. "filter" for the
        # "$filter" alias — see build_input_schema)
        query: Dict[str, Any] = {}
        for param in op["parameters"]:
            client_name = param["name"].lstrip("$")
            if param.get("in") == "query" and client_name in arguments:
                query[param["name"]] = arguments.pop(client_name)

        # Apply default_query and page_size peek-ahead.
        query, current_skip, page_size = apply_query_overrides(query, op)
        logger.debug("LocalTool %s → query=%s page_size=%s", tool_name, query, page_size)

        # Remaining arguments = request body.
        # If the operation expects a body (POST/PUT) but no arguments
        # remain, send an empty dict so FastAPI doesn't reject a missing body.
        body = arguments if arguments else None
        if body is None and op.get("has_body"):
            body = {}

        # A blip (broker hiccup, pool exhaustion, dropped connection) would
        # otherwise surface to the agent as a permanent failure and cost it a
        # whole ReAct iteration to re-plan around. Only retried for server-side
        # and transport faults — a 4xx is the agent's own mistake and repeating
        # it verbatim just fails again.
        last_error: Optional[str] = None
        for attempt in range(_TRANSIENT_RETRIES + 1):
            if attempt:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
                logger.info("Retrying tool %s after transient failure", tool_name)

            try:
                # ASGITransport runs the route on the caller's loop — for the
                # architect that is the SDK background loop. Keep LLM-touching
                # handlers sync `def` so FastAPI offloads them to its threadpool;
                # an `async def` one reaching a run_sync bridge would deadlock it.
                transport = httpx.ASGITransport(app=self._app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://internal"
                ) as client:
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
                    last_error = json.dumps(
                        {
                            "status_code": response.status_code,
                            "detail": detail,
                        },
                        default=str,
                    )
                    if response.status_code >= 500:
                        continue
                    return ToolResult(tool_name=tool_name, success=False, error=last_error)

                try:
                    data = response.json()
                except Exception:
                    data = response.text
                formatted = format_list_response(data, page_size, current_skip)
                return ToolResult(
                    tool_name=tool_name,
                    success=True,
                    content=json.dumps(formatted, default=str),
                )

            except Exception as e:
                logger.error("Local tool execution failed: %s", e, exc_info=True)
                last_error = str(e)

        return ToolResult(tool_name=tool_name, success=False, error=last_error)
