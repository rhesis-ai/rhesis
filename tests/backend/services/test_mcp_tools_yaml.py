"""Tests that mcp_tools.yaml contains expected tools and valid structure."""

import importlib.util
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MCP_TOOLS_YAML = _REPO_ROOT / "apps/backend/src/rhesis/backend/app/mcp_server/mcp_tools.yaml"
_MCP_SCHEMA_PY = _REPO_ROOT / "apps/backend/src/rhesis/backend/app/mcp_server/schema.py"


def load_tool_configs():
    with open(_MCP_TOOLS_YAML) as f:
        return yaml.safe_load(f).get("tools", [])


def _load_schema_module():
    spec = importlib.util.spec_from_file_location("mcp_schema_module", _MCP_SCHEMA_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
class TestExploreEndpointInMcpTools:
    def test_explore_endpoint_in_yaml(self):
        names = [tc["name"] for tc in load_tool_configs()]
        assert "explore_endpoint" in names

    def test_explore_endpoint_is_post(self):
        configs = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = configs["explore_endpoint"]
        assert cfg["method"].upper() == "POST"
        assert "/explore" in cfg["path"]

    def test_explore_endpoint_requires_confirmation(self):
        configs = {tc["name"]: tc for tc in load_tool_configs()}
        assert configs["explore_endpoint"].get("requires_confirmation") is True

    def test_explore_endpoint_has_strategy_and_goal_params(self):
        cfg = {tc["name"]: tc for tc in load_tool_configs()}["explore_endpoint"]
        params = cfg.get("parameters", {})
        assert "strategy" in params
        assert "goal" in params


@pytest.mark.unit
class TestInputSchemaPropertyNames:
    def test_dollar_prefixed_params_are_sanitized(self):
        build_input_schema = _load_schema_module().build_input_schema
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
        assert schema["required"] == ["source_id"]

    def test_yaml_override_keyed_by_sanitized_name_applies(self):
        build_input_schema = _load_schema_module().build_input_schema
        operation = {
            "parameters": [
                {"name": "$filter", "in": "query", "schema": {"type": "string"}},
            ]
        }
        schema = build_input_schema(operation, {}, {"filter": {"description": "search by title"}})
        assert schema["properties"]["filter"]["description"] == "search by title"


@pytest.mark.unit
class TestNewMcpToolsPresent:
    NEW_TOOLS = frozenset({
        "get_test_set",
        "list_test_set_tests",
        "get_endpoint",
        "get_metric",
        "create_source",
        "update_metric",
        "remove_behavior_from_metric",
        "update_test_set",
    })

    def test_new_tools_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        missing = self.NEW_TOOLS - names
        assert not missing, f"Missing tools: {sorted(missing)}"


@pytest.mark.unit
class TestMcpToolsYamlStructure:
    """Every tool entry must declare name, method, and path."""

    EXPECTED_NEW_PATHS = {
        ("get_test_set", "GET", "/test_sets/{test_set_identifier}"),
        ("list_test_set_tests", "GET", "/test_sets/{test_set_identifier}/tests"),
        ("get_endpoint", "GET", "/endpoints/{endpoint_id}"),
        ("get_metric", "GET", "/metrics/{metric_id}"),
        ("create_source", "POST", "/sources/"),
        ("update_metric", "PUT", "/metrics/{metric_id}"),
        ("remove_behavior_from_metric", "DELETE", "/metrics/{metric_id}/behaviors/{behavior_id}"),
        ("update_test_set", "PUT", "/test_sets/{test_set_id}"),
    }

    def test_all_entries_have_required_keys(self):
        for tc in load_tool_configs():
            assert tc.get("name")
            assert tc.get("method")
            assert tc.get("path", "").startswith("/")

    def test_new_tool_paths_configured(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        for name, method, path in self.EXPECTED_NEW_PATHS:
            cfg = by_name[name]
            assert cfg["method"].upper() == method
            assert cfg["path"] == path
