"""Unit tests for the (provider, action) routing table and MCP extract fallback."""

from unittest.mock import AsyncMock, patch

import pytest

from rhesis.backend.app.services.tool.actions import ToolAction, Transport, route
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.mcp.operations import (
    _parse_mcp_auth_response,
    _parse_fetched_sources,
    _strip_code_fence,
    mcp_extract,
    mcp_health_check,
)


class TestRouteTable:
    def test_rest_providers_route_to_rest(self):
        assert route("notion", ToolAction.EXTRACT) is Transport.REST
        assert route("github", ToolAction.EXTRACT) is Transport.REST
        assert route("notion", ToolAction.TEST_CONNECTION) is Transport.REST
        assert route("jira", ToolAction.CREATE_TICKET) is Transport.REST
        assert route("jira", ToolAction.TEST_CONNECTION) is Transport.REST
        assert route("confluence", ToolAction.TEST_CONNECTION) is Transport.REST

    def test_jira_has_no_extract(self):
        with pytest.raises(ToolConfigurationError, match="does not support"):
            route("jira", ToolAction.EXTRACT)

    def test_gitlab_routes_to_mcp(self):
        assert route("gitlab", ToolAction.EXTRACT) is Transport.MCP
        assert route("gitlab", ToolAction.TEST_CONNECTION) is Transport.MCP

    def test_unregistered_provider_raises(self):
        with pytest.raises(ToolConfigurationError, match="does not support"):
            route("unknown", ToolAction.EXTRACT)


class TestParsing:
    def test_strip_plain_json(self):
        assert _strip_code_fence('[{"id": "1"}]') == '[{"id": "1"}]'

    def test_strip_json_fence(self):
        fenced = '```json\n[{"id": "1"}]\n```'
        assert _strip_code_fence(fenced) == '[{"id": "1"}]'

    def test_strip_bare_fence(self):
        assert _strip_code_fence("```\nhello\n```") == "hello"

    def test_parse_valid_array(self):
        raw = '[{"id": "a", "title": "T", "content": "# md", "url": "https://x"}]'
        sources = _parse_fetched_sources(raw)
        assert len(sources) == 1
        assert sources[0].id == "a"
        assert sources[0].title == "T"
        assert sources[0].content == "# md"
        assert sources[0].url == "https://x"

    def test_parse_coerces_missing_fields(self):
        sources = _parse_fetched_sources('[{"content": "body only"}]')
        assert sources[0].id == ""
        assert sources[0].url is None
        assert sources[0].content == "body only"

    def test_parse_non_array_raises(self):
        with pytest.raises(ValueError, match="JSON array"):
            _parse_fetched_sources('{"id": "1"}')

    def test_parse_non_object_element_raises(self):
        with pytest.raises(ValueError, match="JSON object"):
            _parse_fetched_sources('["just a string"]')


_OPS = "rhesis.backend.app.services.tool.mcp.operations"


@pytest.mark.asyncio
class TestMcpExtract:
    _ARGS = dict(
        tool_id="11111111-1111-1111-1111-111111111111",
        identifier="https://example.com/page",
        organization_id="org",
        user_id="user",
    )

    async def test_parses_first_try(self):
        good = {"final_answer": '[{"id": "p1", "title": "Page", "content": "body"}]'}
        with (
            patch(f"{_OPS}._resolve_tool_client", return_value=(object(), "gitlab", None)),
            patch(f"{_OPS}._run_agent", new=AsyncMock(return_value=good)) as run,
        ):
            sources = await mcp_extract(**self._ARGS)
        assert [s.id for s in sources] == ["p1"]
        assert run.await_count == 1

    async def test_repairs_then_parses(self):
        bad = {"final_answer": "Sure! Here is the content..."}
        good = {"final_answer": '[{"id": "p1", "content": "body"}]'}
        with (
            patch(f"{_OPS}._resolve_tool_client", return_value=(object(), "gitlab", None)),
            patch(f"{_OPS}._run_agent", new=AsyncMock(side_effect=[bad, good])) as run,
        ):
            sources = await mcp_extract(**self._ARGS)
        assert [s.id for s in sources] == ["p1"]
        assert run.await_count == 2  # one repair retry

    async def test_repair_exhausted_raises(self):
        bad = {"final_answer": "still not json"}
        with (
            patch(f"{_OPS}._resolve_tool_client", return_value=(object(), "gitlab", None)),
            patch(f"{_OPS}._run_agent", new=AsyncMock(return_value=bad)),
        ):
            with pytest.raises(ValueError, match="did not return valid JSON"):
                await mcp_extract(**self._ARGS)


@pytest.mark.asyncio
class TestMcpHealthCheck:
    async def test_requires_tool_or_params(self):
        with pytest.raises(ToolConfigurationError, match="required to test the connection"):
            await mcp_health_check(organization_id="org", user_id="user")

    async def test_authenticated_saved_tool(self):
        ok = {
            "success": True,
            "final_answer": '{"authenticated": true, "identity": "alice"}',
        }
        with (
            patch(f"{_OPS}._resolve_tool_client", return_value=(object(), "github", None)),
            patch(f"{_OPS}._run_agent", new=AsyncMock(return_value=ok)),
        ):
            result = await mcp_health_check(
                organization_id="org", user_id="user", tool_id="t1"
            )
        assert result["is_authenticated"] == "Yes"
        assert "alice" in result["message"]

    async def test_authenticated_unsaved_credentials(self):
        ok = {"success": True, "final_answer": '{"authenticated": true, "identity": null}'}
        with (
            patch(f"{_OPS}._resolve_params_client", return_value=(object(), "github", None)) as rp,
            patch(f"{_OPS}._run_agent", new=AsyncMock(return_value=ok)),
        ):
            result = await mcp_health_check(
                organization_id="org",
                user_id="user",
                provider_type_id="pt1",
                credentials={"TOKEN": "x"},
            )
        assert result["is_authenticated"] == "Yes"
        assert rp.call_count == 1  # the unsaved-credentials path was used

    async def test_structured_auth_failure(self):
        failed = {
            "success": True,
            "final_answer": '{"authenticated": false, "identity": null, "message": "401 Unauthorized"}',
        }
        with (
            patch(f"{_OPS}._resolve_tool_client", return_value=(object(), "gitlab", None)),
            patch(f"{_OPS}._run_agent", new=AsyncMock(return_value=failed)),
        ):
            result = await mcp_health_check(
                organization_id="org", user_id="user", tool_id="t1"
            )
        assert result["is_authenticated"] == "No"
        assert "401" in result["message"]

    async def test_success_with_auth_failure_answer_is_not_authenticated(self):
        misleading = {
            "success": True,
            "final_answer": '{"authenticated": false, "message": "invalid token"}',
        }
        with (
            patch(f"{_OPS}._resolve_tool_client", return_value=(object(), "gitlab", None)),
            patch(f"{_OPS}._run_agent", new=AsyncMock(return_value=misleading)),
        ):
            result = await mcp_health_check(
                organization_id="org", user_id="user", tool_id="t1"
            )
        assert result["is_authenticated"] == "No"
        assert "invalid token" in result["message"]

    async def test_unstructured_answer_is_not_authenticated(self):
        misleading = {"success": True, "final_answer": "Authentication failed: invalid token"}
        with (
            patch(f"{_OPS}._resolve_tool_client", return_value=(object(), "gitlab", None)),
            patch(f"{_OPS}._run_agent", new=AsyncMock(return_value=misleading)),
        ):
            result = await mcp_health_check(
                organization_id="org", user_id="user", tool_id="t1"
            )
        assert result["is_authenticated"] == "No"
        assert "valid JSON" in result["message"]


class TestMcpAuthResponse:
    def test_parses_structured_success(self):
        result = _parse_mcp_auth_response(
            {"success": True, "final_answer": '{"authenticated": true, "identity": "alice"}'}
        )
        assert result["is_authenticated"] == "Yes"
        assert "alice" in result["message"]

    def test_parses_structured_failure(self):
        result = _parse_mcp_auth_response(
            {
                "success": True,
                "final_answer": '{"authenticated": false, "message": "invalid token"}',
            }
        )
        assert result["is_authenticated"] == "No"
        assert "invalid token" in result["message"]

    def test_rejects_unstructured_failure_markers(self):
        result = _parse_mcp_auth_response(
            {"success": True, "final_answer": "Authentication failed: 401 Unauthorized"}
        )
        assert result["is_authenticated"] == "No"
        assert "valid JSON" in result["message"]
