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
