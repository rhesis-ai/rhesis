"""YAML config loading and MCP Tool / operation-map building.

Reads ``mcp_tools.yaml`` from this package directory, iterates over
configured tools matched against the FastAPI OpenAPI schema, and
produces a list of ``mcp.types.Tool`` objects plus a dispatcher map.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mcp.types as mcp_types
import yaml
from mcp.types import ToolAnnotations

from .schema import build_input_schema

logger = logging.getLogger(__name__)


def load_tool_configs() -> List[dict]:
    """Load tool configurations from the YAML file."""
    yaml_path = Path(__file__).parent / "mcp_tools.yaml"
    with open(yaml_path) as f:
        config = yaml.safe_load(f)
    return config.get("tools", [])


def build_tools_and_operations(
    fastapi_app: Any,
) -> tuple[List[mcp_types.Tool], Dict[str, dict]]:
    """Build MCP Tool objects and an operation map from YAML + OpenAPI.

    Returns:
        (tools_list, operation_map) where operation_map is keyed by
        tool name and contains method, path, and parameters.
    """
    tool_configs = load_tool_configs()
    openapi_schema = fastapi_app.openapi()
    paths = openapi_schema.get("paths", {})

    tools: List[mcp_types.Tool] = []
    operation_map: Dict[str, dict] = {}

    for tc in tool_configs:
        name = tc["name"]
        method = tc["method"].upper()
        path_template = tc["path"]

        path_spec = paths.get(path_template)
        if path_spec is None:
            logger.warning(
                "MCP tool %s: path %s not found in OpenAPI — skipping",
                name,
                path_template,
            )
            continue

        operation = path_spec.get(method.lower())
        if operation is None:
            logger.warning(
                "MCP tool %s: %s %s not in OpenAPI — skipping",
                name,
                method,
                path_template,
            )
            continue

        # YAML parameter description overrides; normalize None values (bare YAML keys) to {}
        raw_overrides = tc.get("parameters", {}) or {}
        yaml_param_overrides = {k: v or {} for k, v in raw_overrides.items()}

        input_schema = build_input_schema(operation, openapi_schema, yaml_param_overrides)

        # When a tool declares page_size, the server controls pagination.
        # Remove 'limit' from the LLM-visible schema so the agent can
        # never override the server-managed page size.
        if tc.get("page_size") is not None:
            input_schema.get("properties", {}).pop("limit", None)
            if "required" in input_schema:
                input_schema["required"] = [r for r in input_schema["required"] if r != "limit"]

        description = tc.get("description", "").strip()

        _readonly_methods = frozenset(("GET", "HEAD", "OPTIONS"))
        annotations = ToolAnnotations(
            readOnlyHint=(method in _readonly_methods),
            destructiveHint=(method in ("DELETE", "PUT")),
            idempotentHint=(method in (*_readonly_methods, "PUT", "DELETE")),
        )
        if "requires_confirmation" in tc:
            annotations.requires_confirmation = tc["requires_confirmation"]

        tools.append(
            mcp_types.Tool(
                name=name,
                description=description,
                inputSchema=input_schema,
                annotations=annotations,
            )
        )

        # Store operation info for the dispatcher
        operation_map[name] = {
            "method": method,
            "path": path_template,
            "parameters": operation.get("parameters", []),
            "has_body": "requestBody" in operation,
            "default_query": tc.get("default_query", {}),
            "page_size": tc.get("page_size"),
            "count_check": tc.get("count_check"),
        }

    return tools, operation_map


def load_tool_labels() -> Dict[str, str]:
    """Load tool name -> UI label mapping from the YAML file."""
    return {tc["name"]: tc["label"] for tc in load_tool_configs() if "label" in tc}


# ── Shared query / response helpers ───────────────────────────────


def apply_query_overrides(
    query: Dict[str, Any],
    op: Dict[str, Any],
) -> Tuple[Dict[str, Any], int, Optional[int]]:
    """Apply default_query and page_size peek-ahead to query params.

    ``default_query`` fills in keys the caller did not supply.
    ``page_size`` enforces server-controlled pagination via peek-ahead
    (request one extra item to detect whether more results exist).

    Returns ``(updated_query, current_skip, page_size)``.
    ``page_size`` is ``None`` when the tool does not declare pagination.
    """
    # default_query: applied only when the caller did not already set the key
    for key, value in op.get("default_query", {}).items():
        if key not in query:
            query[key] = value

    # peek-ahead pagination: request one extra item to detect has_more
    page_size: Optional[int] = op.get("page_size")
    current_skip: int = 0
    if page_size is not None:
        current_skip = int(query.get("skip", 0))
        query["limit"] = page_size + 1

    return query, current_skip, page_size


def annotate_write_count(
    data: Any,
    body: Optional[Dict[str, Any]],
    op: Dict[str, Any],
) -> Any:
    """Say so in the response when a write created fewer rows than it was sent.

    A bulk create answers with the count it actually wrote, and an agent that
    reports the number it asked for instead is not contradicted by anything.
    Issue #2516 was exactly that: 95 tests requested, 8 written, 95 reported,
    and nothing in the exchange said otherwise.

    Declared per tool in ``mcp_tools.yaml`` as
    ``count_check: {request_list: <body key>, response_count: <response key>}``.
    Leaves the response untouched when the tool declares no check, when either
    side is missing, or when the counts agree.
    """
    check = op.get("count_check")
    if not isinstance(check, dict) or not isinstance(data, dict) or not isinstance(body, dict):
        return data

    request_list = check.get("request_list")
    response_count = check.get("response_count")
    if not request_list or not response_count:
        return data

    requested = body.get(request_list)
    written = data.get(response_count)
    if not isinstance(requested, list) or not isinstance(written, int):
        return data
    if len(requested) == written:
        return data

    data = dict(data)
    data["_count_check"] = {
        "requested": len(requested),
        "written": written,
        "warning": (
            f"Sent {len(requested)} but {written} were created. Report {written}, "
            "the number in this response, not the number you asked for. Say that "
            "the rest were not created and stop rather than describing them."
        ),
    }
    return data


def format_list_response(
    data: Any,
    page_size: Optional[int],
    current_skip: int,
) -> Any:
    """Wrap a list response with ``_pagination`` metadata when page_size is set.

    If ``data`` is not a list, or ``page_size`` is ``None``, the data is
    returned unchanged so non-list responses (single objects, stats dicts,
    errors) pass through without modification.
    """
    if page_size is None or not isinstance(data, list):
        return data

    has_more = len(data) > page_size
    items = data[:page_size]
    meta: Dict[str, Any] = {"returned": len(items), "has_more": has_more}
    if has_more:
        meta["next_skip"] = current_skip + page_size
        meta["hint"] = (
            f"Showing {len(items)} results — there are more. "
            "Use $filter to narrow (e.g. $filter=name eq 'x') "
            f"or call again with skip={meta['next_skip']} for the next page."
        )
    elif not items and not current_skip:
        # An empty page is the answer, and saying so beats handing back a bare
        # []. A model given nothing tends to fill the gap -- issue #2402 was
        # exactly that, an agent inventing reviews for a run whose annotations
        # it could not read. Stating the emptiness gives it something true to
        # relay instead.
        meta["hint"] = (
            "No results matched. This is the answer: report that none exist "
            "for these filters. Do not describe results you did not receive."
        )
    return {"results": items, "_pagination": meta}
