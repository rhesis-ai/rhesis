"""YAML config loading and MCP Tool / operation-map building.

Reads ``mcp_tools.yaml`` from this package directory, iterates over
configured tools matched against the FastAPI OpenAPI schema, and
produces a list of ``mcp.types.Tool`` objects plus a dispatcher map.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import mcp.types as mcp_types
import yaml

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

        # YAML parameter description overrides
        yaml_param_overrides = tc.get("parameters", {}) or {}

        input_schema = build_input_schema(operation, openapi_schema, yaml_param_overrides)
        description = tc.get("description", "").strip()

        tools.append(
            mcp_types.Tool(
                name=name,
                description=description,
                inputSchema=input_schema,
            )
        )

        # Store operation info for the dispatcher
        operation_map[name] = {
            "method": method,
            "path": path_template,
            "parameters": operation.get("parameters", []),
            "has_body": "requestBody" in operation,
        }

    return tools, operation_map
