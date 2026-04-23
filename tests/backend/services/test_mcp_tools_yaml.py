"""Tests that mcp_tools.yaml contains the expected explore_endpoint entry.

Validates that ``build_tools_and_operations`` exposes ``explore_endpoint``
in the MCP tool list with the correct HTTP method and path.
"""

import pytest


@pytest.mark.unit
class TestExploreEndpointInMcpTools:
    def test_explore_endpoint_registered(self):
        """explore_endpoint must appear in the MCP tool list."""
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        mock_app = object()  # build_tools_and_operations only needs app for ASGI transport
        tools, operation_map = build_tools_and_operations(mock_app)

        tool_names = [t.name for t in tools]
        assert "explore_endpoint" in tool_names, (
            f"explore_endpoint not found in MCP tool list. Registered tools: {tool_names}"
        )

    def test_explore_endpoint_is_post(self):
        """explore_endpoint must map to POST /endpoints/{endpoint_id}/explore."""
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        mock_app = object()
        _, operation_map = build_tools_and_operations(mock_app)

        op = operation_map.get("explore_endpoint")
        assert op is not None, "explore_endpoint not found in operation_map"
        assert op["method"] == "POST"
        assert "/explore" in op["path"]

    def test_explore_endpoint_requires_confirmation(self):
        """explore_endpoint must have requires_confirmation=True (it's a write action)."""
        from rhesis.backend.app.mcp_server.tools import load_tool_configs

        configs = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = configs.get("explore_endpoint")
        assert cfg is not None, "explore_endpoint not found in mcp_tools.yaml"
        assert cfg.get("requires_confirmation") is True

    def test_explore_endpoint_schema_has_strategy_and_goal(self):
        """explore_endpoint inputSchema must expose strategy and goal as parameters."""
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        mock_app = object()
        tools, _ = build_tools_and_operations(mock_app)

        tool = next((t for t in tools if t.name == "explore_endpoint"), None)
        assert tool is not None

        properties = tool.inputSchema.get("properties", {})
        assert "strategy" in properties, "strategy parameter missing from explore_endpoint schema"
        assert "goal" in properties, "goal parameter missing from explore_endpoint schema"
