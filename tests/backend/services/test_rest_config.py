"""Tests for the REST provider registry — build_client and get_rest_source."""

import uuid
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.tool.rest.config import build_client, get_rest_source
from rhesis.backend.app.services.tool.rest.confluence import ConfluenceRestClient
from rhesis.backend.app.services.tool.rest.github import GitHubRestClient
from rhesis.backend.app.services.tool.rest.jira import JiraRestClient
from rhesis.backend.app.services.tool.rest.notion import NotionRestClient
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp.exceptions import MCPConfigurationError


@pytest.mark.unit
@pytest.mark.services
class TestBuildClient:
    """Test build_client provider → client resolution."""

    def test_notion(self):
        client = build_client("notion", {"NOTION_TOKEN": "tok"})
        assert isinstance(client, NotionRestClient)

    def test_github(self):
        client = build_client("github", {"GITHUB_PERSONAL_ACCESS_TOKEN": "tok"})
        assert isinstance(client, GitHubRestClient)

    def test_jira(self):
        client = build_client(
            "jira",
            {"JIRA_URL": "u", "JIRA_USERNAME": "n", "JIRA_API_TOKEN": "t"},
        )
        assert isinstance(client, JiraRestClient)

    def test_confluence(self):
        client = build_client(
            "confluence",
            {"CONFLUENCE_URL": "u", "CONFLUENCE_USERNAME": "n", "CONFLUENCE_API_TOKEN": "t"},
        )
        assert isinstance(client, ConfluenceRestClient)

    def test_unknown_provider_raises(self):
        with pytest.raises(MCPConfigurationError, match="No REST client registered"):
            build_client("slack", {})


@pytest.mark.unit
@pytest.mark.services
class TestGetRestSource:
    """Test get_rest_source DB → client resolution and error handling."""

    def _tool(self, provider="notion", credentials='{"NOTION_TOKEN": "tok"}'):
        tool = Mock()
        tool.tool_provider_type.type_value = provider
        tool.credentials = credentials
        return tool

    def test_resolves_client(self):
        db = Mock(spec=Session)
        org_id = str(uuid.uuid4())
        tool_id = str(uuid.uuid4())
        with patch(
            "rhesis.backend.app.services.tool.rest.config.crud"
        ) as mock_crud:
            mock_crud.get_tool.return_value = self._tool("github", '{"X": "y"}')
            client = get_rest_source(db, tool_id, org_id)
        assert isinstance(client, GitHubRestClient)

    def test_tool_not_found_raises(self):
        db = Mock(spec=Session)
        with patch(
            "rhesis.backend.app.services.tool.rest.config.crud"
        ) as mock_crud:
            mock_crud.get_tool.return_value = None
            with pytest.raises(MCPConfigurationError, match="not found"):
                get_rest_source(db, str(uuid.uuid4()), str(uuid.uuid4()))

    def test_deleted_tool_raises(self):
        db = Mock(spec=Session)
        with patch(
            "rhesis.backend.app.services.tool.rest.config.crud"
        ) as mock_crud:
            mock_crud.get_tool.side_effect = ItemDeletedException("Tool", "gone")
            with pytest.raises(MCPConfigurationError, match="has been deleted"):
                get_rest_source(db, str(uuid.uuid4()), str(uuid.uuid4()))

    def test_invalid_credentials_json_raises(self):
        db = Mock(spec=Session)
        with patch(
            "rhesis.backend.app.services.tool.rest.config.crud"
        ) as mock_crud:
            mock_crud.get_tool.return_value = self._tool(credentials="not json{")
            with pytest.raises(MCPConfigurationError, match="Invalid credentials"):
                get_rest_source(db, str(uuid.uuid4()), str(uuid.uuid4()))
