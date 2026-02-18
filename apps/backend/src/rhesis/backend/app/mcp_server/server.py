"""MCP server creation, request dispatching, and FastAPI integration.

Creates the low-level ``MCPServer``, registers the tool-list and
call-tool handlers (single dispatcher), and mounts the server on
the FastAPI application via ``StreamableHTTPSessionManager``.
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx
import mcp.types as mcp_types
from fastapi.security import HTTPAuthorizationCredentials
from mcp.server.lowlevel.server import Server as MCPServer
from mcp.server.lowlevel.server import request_ctx
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from rhesis.backend.app.auth.auth_utils import (
    get_authenticated_user_with_context,
    get_secret_key,
)

from .tools import build_tools_and_operations

logger = logging.getLogger(__name__)


# ── Response formatters ────────────────────────────────────────────


def format_success(response: httpx.Response) -> str:
    """Format a successful response as a JSON string for MCP."""
    try:
        data = response.json()
    except Exception:
        data = response.text
    return json.dumps(data, default=str)


def format_error(response: httpx.Response) -> str:
    """Format an error response as a JSON string for MCP."""
    try:
        detail = response.json()
    except Exception:
        detail = response.text
    error = {
        "error": True,
        "status_code": response.status_code,
        "detail": detail,
    }
    return json.dumps(error, default=str)


# ── MCP server factory ─────────────────────────────────────────────


def _create_mcp_server(fastapi_app: Any) -> MCPServer:
    """Create the low-level MCP Server with tool handlers."""
    tools, operation_map = build_tools_and_operations(fastapi_app)

    server = MCPServer(
        name="Rhesis",
        instructions=(
            "Rhesis platform API tools. Use these to create and manage "
            "projects, test sets, tests, test configurations, test "
            "runs, and view results."
        ),
    )

    @server.list_tools()
    async def handle_list_tools() -> list[mcp_types.Tool]:
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
        op = operation_map.get(name)
        if op is None:
            return [
                mcp_types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": True,
                            "detail": f"Unknown tool: {name}",
                        }
                    ),
                )
            ]

        arguments = dict(arguments)  # copy to pop from

        # Extract auth from MCP request context (the original HTTP
        # request that carried this MCP message).
        headers: Dict[str, str] = {}
        try:
            ctx = request_ctx.get()
            request: Optional[Request] = getattr(ctx, "request", None)
            if request is not None:
                auth_value = request.headers.get("authorization", "")
                if auth_value:
                    headers["Authorization"] = auth_value
        except LookupError:
            pass

        # 1. Path params: pop from arguments, substitute in URL
        path = op["path"]
        for param in op["parameters"]:
            if param.get("in") == "path" and param["name"] in arguments:
                path = path.replace(
                    f"{{{param['name']}}}",
                    str(arguments.pop(param["name"])),
                )

        # 2. Query params: pop from arguments
        query: Dict[str, Any] = {}
        for param in op["parameters"]:
            if param.get("in") == "query" and param["name"] in arguments:
                query[param["name"]] = arguments.pop(param["name"])

        # 3. Remaining arguments = request body
        body = arguments if arguments else None

        # 4. Proxy via httpx ASGITransport (in-process)
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mcp-internal") as client:
            response = await client.request(
                method=op["method"],
                url=path,
                headers=headers,
                params=query,
                json=body,
            )

        if response.status_code >= 400:
            text = format_error(response)
        else:
            text = format_success(response)

        return [mcp_types.TextContent(type="text", text=text)]

    logger.info("MCP server initialized with %d tools", len(tools))
    return server


# ── FastAPI integration ────────────────────────────────────────────


def setup_mcp_server(
    fastapi_app: Any,
) -> StreamableHTTPSessionManager:
    """Create MCP server and mount it on the FastAPI application.

    Returns the ``StreamableHTTPSessionManager`` so the caller can
    start it in the application lifespan (``async with sm.run()``).
    FastAPI's ``Mount`` does not propagate lifespan events to
    sub-applications, so the session manager must be started by
    the parent app.
    """
    mcp_server = _create_mcp_server(fastapi_app)

    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        stateless=True,
        security_settings=TransportSecuritySettings(
            # DNS rebinding protection is unnecessary here: the MCP
            # server is mounted in-process via ASGI transport (no
            # actual network hop), so Host header validation adds no
            # security value and would break internal httpx calls.
            enable_dns_rebinding_protection=False,
        ),
    )

    # ASGI wrapper that validates auth before delegating to the
    # session manager.  MCP uses raw ASGI (not FastAPI routes), so
    # AuthenticatedAPIRoute doesn't apply — we check the bearer
    # token ourselves.
    class _MCPApp:
        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] == "http":
                request = Request(scope, receive, send)
                auth_header = request.headers.get("authorization", "")
                credentials: Optional[HTTPAuthorizationCredentials] = None
                if auth_header.lower().startswith("bearer "):
                    credentials = HTTPAuthorizationCredentials(
                        scheme="Bearer",
                        credentials=auth_header[7:],
                    )

                try:
                    secret_key = get_secret_key()
                except Exception:
                    secret_key = None

                user = await get_authenticated_user_with_context(
                    request,
                    credentials=credentials,
                    secret_key=secret_key,
                )
                if user is None:
                    response = JSONResponse(
                        status_code=401,
                        content={"detail": "Authentication required"},
                    )
                    await response(scope, receive, send)
                    return

            await session_manager.handle_request(scope, receive, send)

    fastapi_app.mount("/mcp", _MCPApp())

    # Store reference so the parent app's lifespan can start it
    fastapi_app.state.mcp_session_manager = session_manager

    logger.info("MCP endpoint mounted at /mcp")
    return session_manager
