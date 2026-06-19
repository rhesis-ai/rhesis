"""Tests that mcp_tools.yaml contains the expected explore_endpoint entry."""

import pytest


@pytest.mark.unit
class TestExploreEndpointInMcpTools:
    def test_explore_endpoint_in_yaml(self):
        """explore_endpoint must appear in the raw tool config list."""
        from rhesis.backend.app.mcp_server.tools import load_tool_configs

        names = [tc["name"] for tc in load_tool_configs()]
        assert "explore_endpoint" in names, (
            f"explore_endpoint not found in mcp_tools.yaml. Found: {names}"
        )

    def test_explore_endpoint_is_post(self):
        """explore_endpoint must be configured as POST /endpoints/{endpoint_id}/explore."""
        from rhesis.backend.app.mcp_server.tools import load_tool_configs

        configs = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = configs.get("explore_endpoint")
        assert cfg is not None
        assert cfg["method"].upper() == "POST"
        assert "/explore" in cfg["path"]

    def test_explore_endpoint_requires_confirmation(self):
        """explore_endpoint must have requires_confirmation=True."""
        from rhesis.backend.app.mcp_server.tools import load_tool_configs

        configs = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = configs.get("explore_endpoint")
        assert cfg is not None
        assert cfg.get("requires_confirmation") is True

    def test_explore_endpoint_has_strategy_and_goal_params(self):
        """explore_endpoint parameters must declare strategy and goal."""
        from rhesis.backend.app.mcp_server.tools import load_tool_configs

        configs = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = configs.get("explore_endpoint")
        assert cfg is not None
        params = cfg.get("parameters", {})
        assert "strategy" in params, "strategy parameter missing from explore_endpoint"
        assert "goal" in params, "goal parameter missing from explore_endpoint"


@pytest.mark.unit
class TestInputSchemaPropertyNames:
    """Generated tool-schema property names must satisfy the Anthropic API.

    Property keys must match ``^[a-zA-Z0-9_.-]{1,64}$``; OData aliases like
    ``$filter``/``$select`` would otherwise get the whole tool list rejected.
    """

    def test_dollar_prefixed_params_are_sanitized(self):
        from rhesis.backend.app.mcp_server.schema import build_input_schema

        operation = {
            "parameters": [
                {"name": "$filter", "in": "query", "schema": {"type": "string"}},
                {"name": "$select", "in": "query", "schema": {"type": "string"}},
                {"name": "source_id", "in": "path", "required": True},
            ]
        }
        schema = build_input_schema(operation, {}, {})

        props = schema["properties"]
        assert "filter" in props and "$filter" not in props
        assert "select" in props and "$select" not in props
        assert "source_id" in props
        assert schema["required"] == ["source_id"]

    def test_yaml_override_keyed_by_sanitized_name_applies(self):
        from rhesis.backend.app.mcp_server.schema import build_input_schema

        operation = {
            "parameters": [
                {"name": "$filter", "in": "query", "schema": {"type": "string"}},
            ]
        }
        schema = build_input_schema(operation, {}, {"filter": {"description": "search by title"}})

        assert schema["properties"]["filter"]["description"] == "search by title"
