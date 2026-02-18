"""MCP server endpoint for the Rhesis backend.

Exposes Rhesis CRUD operations as MCP tools, auto-generated from
FastAPI routes using a YAML configuration file. Each tool proxies
requests to the real FastAPI app via httpx ASGITransport (in-process,
no network hop), reusing all existing validation, auth, and logic.
"""

import contextvars
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Bearer token extracted from the incoming MCP HTTP request,
# forwarded on proxied calls to the FastAPI app.
_auth_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_auth_token", default=None
)

# ── OpenAPI type → Python type mapping ──────────────────────────────

_OPENAPI_TYPE_MAP: Dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


# ── Auth middleware ─────────────────────────────────────────────────


class MCPAuthMiddleware:
    """ASGI middleware that captures the Bearer token from incoming
    MCP HTTP requests and stores it in a contextvar for forwarding."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            auth_value = headers.get(b"authorization", b"").decode()
            if auth_value.lower().startswith("bearer "):
                token = _auth_token.set(auth_value)
                try:
                    await self.app(scope, receive, send)
                finally:
                    _auth_token.reset(token)
                return
        await self.app(scope, receive, send)


# ── Tool builder ───────────────────────────────────────────────────


def _extract_path_params(path: str) -> List[str]:
    """Extract {param} names from a URL path template."""
    return re.findall(r"\{(\w+)\}", path)


def _resolve_route_spec(
    openapi_schema: dict,
    method: str,
    path: str,
) -> Optional[dict]:
    """Find the OpenAPI operation spec for a given method + path."""
    paths = openapi_schema.get("paths", {})
    path_spec = paths.get(path)
    if path_spec is None:
        return None
    return path_spec.get(method.lower())


def _sanitize_param_name(name: str) -> str:
    """Turn an OpenAPI parameter name into a valid Python identifier.

    E.g. ``$filter`` → ``filter``.
    """
    sanitized = re.sub(r"[^\w]", "", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"p_{sanitized}"
    return sanitized or "param"


def _build_param_list(
    operation: dict,
    path_params: List[str],
) -> List[Dict[str, Any]]:
    """Build a list of parameter dicts from the OpenAPI operation.

    Each dict has: name (Python-safe), api_name (original), python_type,
    required, default, description.
    """
    params: List[Dict[str, Any]] = []

    # Query / path parameters from OpenAPI "parameters" array
    for p in operation.get("parameters", []):
        api_name = p["name"]
        name = _sanitize_param_name(api_name)
        schema = p.get("schema", {})
        openapi_type = schema.get("type", "string")
        python_type = _OPENAPI_TYPE_MAP.get(openapi_type, str)
        required = p.get("required", api_name in path_params)
        default = schema.get("default")
        description = p.get("description", "")

        # Skip internal FastAPI dependencies (db, tenant, user)
        if api_name in (
            "db",
            "tenant_context",
            "current_user",
            "response",
            "_validate_workers",
            "_validate_model",
        ):
            continue

        params.append(
            {
                "name": name,
                "api_name": api_name,
                "python_type": python_type,
                "required": required,
                "default": default,
                "description": description,
            }
        )

    return params


def _build_tool_function(
    fastapi_app: Any,
    tool_config: dict,
    openapi_schema: dict,
) -> Optional[Any]:
    """Generate an async tool function for a single YAML tool entry.

    Uses exec() to create a function with a proper typed signature
    so FastMCP generates correct JSON Schema for the tool's input.
    """
    name = tool_config["name"]
    method = tool_config["method"].upper()
    path_template = tool_config["path"]
    path_params = _extract_path_params(path_template)

    operation = _resolve_route_spec(openapi_schema, method, path_template)
    if operation is None:
        logger.warning(
            "MCP tool %s: no OpenAPI spec found for %s %s — skipping",
            name,
            method,
            path_template,
        )
        return None

    # Collect query / path parameters
    params = _build_param_list(operation, path_params)

    # Check whether this route has a request body
    has_body = "requestBody" in operation

    # ── Build function signature pieces ────────────────────────

    sig_parts: List[str] = []
    # Required params first (no default)
    for p in sorted(params, key=lambda x: not x["required"]):
        type_name = p["python_type"].__name__
        if p["required"]:
            sig_parts.append(f"{p['name']}: {type_name}")
        else:
            default_repr = repr(p["default"])
            sig_parts.append(f"{p['name']}: {type_name} = {default_repr}")

    if has_body:
        # Accept body as a dict OR as individual keyword arguments.
        # LLMs sometimes pass {"body": {...}} and sometimes pass the
        # body fields directly as top-level arguments.
        sig_parts.append("body: dict = None")
        sig_parts.append("**kwargs")

    sig_str = ", ".join(sig_parts)

    # ── Build function body ────────────────────────────────────

    body_lines = []

    # If body is None but kwargs were passed, use kwargs as body
    if has_body:
        body_lines.extend(
            [
                "    if body is None and kwargs:",
                "        body = kwargs",
            ]
        )

    body_lines.extend(
        [
            "    auth = _auth_token.get()",
            "    headers = {}",
            "    if auth:",
            '        headers["Authorization"] = auth',
            f"    path = {path_template!r}",
        ]
    )

    # Interpolate path parameters
    for pp in path_params:
        body_lines.append(f"    path = path.replace('{{{pp}}}', str({pp}))")

    # Build query params dict — use api_name as the HTTP key,
    # but the sanitized name as the Python variable reference.
    query_params = [p for p in params if p["name"] not in path_params]
    if query_params:
        body_lines.append("    query_params = {}")
        for qp in query_params:
            py_name = qp["name"]
            api_name = qp["api_name"]
            body_lines.append(f"    if {py_name} is not None:")
            body_lines.append(f"        query_params[{api_name!r}] = {py_name}")
    else:
        body_lines.append("    query_params = {}")

    # httpx request via ASGITransport
    body_lines.extend(
        [
            "    transport = httpx.ASGITransport(app=_fastapi_app)",
            "    async with httpx.AsyncClient(transport=transport, "
            'base_url="http://mcp-internal") as client:',
            "        response = await client.request(",
            f"            method={method!r},",
            "            url=path,",
            "            headers=headers,",
            "            params=query_params,",
        ]
    )

    if has_body:
        body_lines.append("            json=body,")

    body_lines.extend(
        [
            "        )",
            "    if response.status_code >= 400:",
            "        return _format_error(response)",
            "    return _format_success(response)",
        ]
    )

    func_code = f"async def {name}({sig_str}):\n" + "\n".join(body_lines)

    # ── Execute to create the function object ──────────────────

    local_ns: Dict[str, Any] = {}
    global_ns: Dict[str, Any] = {
        "httpx": httpx,
        "_auth_token": _auth_token,
        "_fastapi_app": fastapi_app,
        "_format_error": _format_error,
        "_format_success": _format_success,
        "Optional": Optional,
    }

    try:
        exec(func_code, global_ns, local_ns)  # noqa: S102
    except SyntaxError:
        logger.error(
            "MCP tool %s: failed to compile function:\n%s",
            name,
            func_code,
        )
        return None

    func = local_ns[name]
    func.__doc__ = tool_config.get("description", "")
    return func


# ── Response formatters ────────────────────────────────────────────


def _format_success(response: httpx.Response) -> str:
    """Format a successful response as a JSON string for MCP."""
    try:
        data = response.json()
    except Exception:
        data = response.text
    return json.dumps(data, default=str)


def _format_error(response: httpx.Response) -> str:
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


# ── Tool registration ─────────────────────────────────────────────


def _load_tool_configs() -> List[dict]:
    """Load tool configurations from the YAML file."""
    yaml_path = Path(__file__).parent / "mcp_tools.yaml"
    with open(yaml_path) as f:
        config = yaml.safe_load(f)
    return config.get("tools", [])


def register_mcp_tools(
    mcp: Any,
    fastapi_app: Any,
) -> int:
    """Register all tools from mcp_tools.yaml on the FastMCP server.

    Returns the number of tools successfully registered.
    """
    tool_configs = _load_tool_configs()
    openapi_schema = fastapi_app.openapi()
    registered = 0

    for tool_config in tool_configs:
        func = _build_tool_function(fastapi_app, tool_config, openapi_schema)
        if func is None:
            continue

        description = tool_config.get("description", "").strip()
        mcp.add_tool(func, name=tool_config["name"], description=description)
        registered += 1
        logger.debug("MCP tool registered: %s", tool_config["name"])

    return registered


# ── Factory ────────────────────────────────────────────────────────

# The session manager must be started/stopped by the parent app's
# lifespan since FastAPI Mount doesn't propagate lifespan events.
_mcp_session_manager = None


def get_mcp_session_manager():
    """Return the MCP session manager for lifespan management.

    Call ``async with get_mcp_session_manager().run():`` in the parent
    FastAPI app's lifespan to initialize the session manager's task group.
    """
    return _mcp_session_manager


def create_mcp_app(fastapi_app: Any) -> ASGIApp:
    """Create the MCP ASGI app to be mounted on the FastAPI application.

    Returns a Starlette app that handles the MCP protocol at the mount
    point (typically ``/mcp``).

    **Important:** After mounting, call ``get_mcp_session_manager().run()``
    as an async context manager in the parent app's lifespan. FastAPI's
    ``Mount`` does not propagate lifespan to sub-apps, so the MCP session
    manager must be started externally.
    """
    global _mcp_session_manager

    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings

    mcp = FastMCP(
        name="Rhesis",
        instructions=(
            "Rhesis platform API tools. Use these to create and manage "
            "projects, test sets, tests, test configurations, test runs, "
            "and view results."
        ),
        stateless_http=True,
        # Route is "/" since FastAPI mounts us at /mcp — the full
        # external URL is /mcp, not /mcp/mcp.
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    count = register_mcp_tools(mcp, fastapi_app)
    logger.info("MCP server initialized with %d tools", count)

    # Get the Starlette app for streamable HTTP
    starlette_app = mcp.streamable_http_app()

    # Store session manager so the parent app's lifespan can start it.
    _mcp_session_manager = mcp.session_manager

    # Inject auth middleware into the Starlette app's middleware stack.
    starlette_app.add_middleware(MCPAuthMiddleware)

    return starlette_app
