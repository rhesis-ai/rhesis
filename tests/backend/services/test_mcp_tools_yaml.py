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
    assert spec and spec.loader, f"Could not load schema module from {_MCP_SCHEMA_PY}"
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
    NEW_TOOLS = frozenset(
        {
            "get_test_set",
            "list_test_set_tests",
            "get_endpoint",
            "get_metric",
            "create_source",
            "update_metric",
            "remove_behavior_from_metric",
            "update_test_set",
            "get_test",
            "update_test",
            "get_behavior",
            "get_test_set_last_run",
            "get_test_set_metrics",
            "get_project",
        }
    )

    def test_new_tools_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        missing = self.NEW_TOOLS - names
        assert not missing, f"Missing tools: {sorted(missing)}"


@pytest.mark.unit
class TestTagMcpToolsPresent:
    TAG_TOOLS = frozenset({"list_tags", "assign_tag"})

    def test_tag_tools_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        missing = self.TAG_TOOLS - names
        assert not missing, f"Missing tag tools: {sorted(missing)}"

    def test_assign_tag_path_and_method(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = by_name["assign_tag"]
        assert cfg["method"].upper() == "POST"
        assert cfg["path"] == "/tags/{entity_type}/{entity_id}"

    def test_list_tags_default_query_select(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = by_name["list_tags"]
        assert cfg.get("default_query", {}).get("$select") == "id,name"

    def test_assign_tag_requires_confirmation(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        assert by_name["assign_tag"].get("requires_confirmation") is True


@pytest.mark.unit
class TestListAnnotationsTool:
    """The annotations tool is how the architect sees human review feedback."""

    def _cfg(self):
        return {tc["name"]: tc for tc in load_tool_configs()}["list_annotations"]

    def test_list_annotations_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        assert "list_annotations" in names

    def test_list_annotations_is_read_only_get(self):
        cfg = self._cfg()
        assert cfg["method"].upper() == "GET"
        # GET gets readOnlyHint automatically, so it must not be confirmation-gated.
        assert "requires_confirmation" not in cfg

    def test_list_annotations_path_has_trailing_slash(self):
        # Must match the OpenAPI path key exactly or the tool is silently skipped.
        assert self._cfg()["path"] == "/annotations/"

    def test_list_annotations_declares_page_size(self):
        page_size = self._cfg().get("page_size")
        assert page_size is not None
        # peek-ahead sends limit=page_size+1, which must stay within the
        # endpoint's le=100 cap.
        assert page_size + 1 <= 100

    def test_list_annotations_description_documents_scoping(self):
        description = self._cfg()["description"]
        for token in ("test_run_id", "test_result_id", "trace_id", "trace_db_id"):
            assert token in description, f"description should explain {token}"

    def test_list_annotations_input_schema_exposes_filters(self):
        """Build the schema from the real app so a path/param drift fails here."""
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, operations = build_tools_and_operations(app)
        by_name = {t.name: t for t in tools}
        assert "list_annotations" in by_name, (
            "tool absent — path likely does not match any OpenAPI route"
        )

        props = by_name["list_annotations"].inputSchema["properties"]
        for param in (
            "test_run_id",
            "test_result_id",
            "trace_id",
            "trace_db_id",
            "resolved",
            "rating",
            "source",
            "target_type",
            "skip",
        ):
            assert param in props, f"{param} missing from tool schema"

        # page_size means the server owns pagination.
        assert "limit" not in props
        assert operations["list_annotations"]["method"] == "GET"

    def test_list_annotations_is_readonly_hinted(self):
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, _ = build_tools_and_operations(app)
        tool = {t.name: t for t in tools}["list_annotations"]
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


@pytest.mark.unit
class TestCreateMetricDocumentsDescriptiveFields:
    """A metric the architect creates must be rich, not just scoreable.

    These fields exist on MetricCreate but carry no Pydantic descriptions,
    so the YAML overrides are the only thing telling the agent to fill
    them. Without them the agent sends name + evaluation_prompt only.
    """

    RICH_FIELDS = ("description", "evaluation_steps", "reasoning", "explanation")

    def _cfg(self):
        return {tc["name"]: tc for tc in load_tool_configs()}["create_metric"]

    def test_descriptive_fields_are_documented(self):
        params = self._cfg().get("parameters", {})
        missing = [f for f in self.RICH_FIELDS if f not in params]
        assert not missing, f"create_metric does not document: {missing}"

    def test_descriptive_field_docs_are_substantive(self):
        params = self._cfg()["parameters"]
        for field in self.RICH_FIELDS:
            text = (params[field] or {}).get("description", "")
            assert len(text.strip()) > 40, f"{field} needs a real description, got: {text!r}"

    def test_tool_description_demands_rich_metrics(self):
        description = self._cfg()["description"]
        for field in self.RICH_FIELDS:
            assert field in description, f"description should name {field}"

    def test_descriptive_fields_reach_the_tool_schema(self):
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, _ = build_tools_and_operations(app)
        props = {t.name: t for t in tools}["create_metric"].inputSchema["properties"]
        for field in self.RICH_FIELDS:
            assert field in props, f"{field} absent from create_metric schema"
            assert props[field].get("description"), (
                f"{field} reached the schema with no description — the agent "
                "has no reason to fill it"
            )


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
        ("update_test_set", "PUT", "/test_sets/{test_set_identifier}"),
        ("get_test", "GET", "/tests/{test_id}"),
        ("update_test", "PUT", "/tests/{test_id}"),
        ("get_behavior", "GET", "/behaviors/{behavior_id}"),
        ("get_test_set_last_run", "GET", "/test_sets/{test_set_identifier}/last-run/{endpoint_id}"),
        ("get_test_set_metrics", "GET", "/test_sets/{test_set_identifier}/metrics"),
        ("get_project", "GET", "/projects/{project_id}"),
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
