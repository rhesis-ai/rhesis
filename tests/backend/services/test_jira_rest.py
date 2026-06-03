"""Tests for Jira REST service — create_jira_ticket_from_task."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.tool.rest import create_jira_ticket_from_task
from rhesis.backend.app.services.tool.rest.jira import JiraRestClient
from rhesis.backend.app.services.tool.rest.notion import NotionSource


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestCreateJiraTicketFromTask:
    """Test create_jira_ticket_from_task REST function."""

    async def test_create_jira_ticket_success(self):
        """Successfully create Jira ticket from task."""
        task_id = uuid.uuid4()
        tool_id = str(uuid.uuid4())
        db = Mock(spec=Session)

        mock_task = Mock()
        mock_task.title = "Test Task"
        mock_task.description = "Task description"
        mock_task.task_metadata = {}

        mock_tool = Mock()
        mock_tool.tool_metadata = {"space_key": "PROJ"}

        mock_jira_client = Mock(spec=JiraRestClient)
        mock_jira_client.create_issue = AsyncMock(
            return_value={
                "issue_key": "PROJ-123",
                "issue_url": "https://jira.example.com/browse/PROJ-123",
            }
        )

        with (
            patch(
                "rhesis.backend.app.services.tool.rest.jira.crud"
            ) as mock_crud,
            patch(
                "rhesis.backend.app.services.tool.rest.jira.get_rest_source",
                return_value=mock_jira_client,
            ),
        ):
            mock_crud.get_task.return_value = mock_task
            mock_crud.get_tool.return_value = mock_tool

            result = await create_jira_ticket_from_task(task_id, tool_id, db, "org", "user")

        assert result["issue_key"] == "PROJ-123"
        assert result["issue_url"] == "https://jira.example.com/browse/PROJ-123"
        assert "jira_issue" in mock_task.task_metadata
        assert mock_task.task_metadata["jira_issue"]["issue_key"] == "PROJ-123"
        assert mock_task.task_metadata["jira_issue"]["tool_id"] == tool_id

    async def test_create_jira_ticket_task_not_found(self):
        """Raises ValueError when task not found."""
        task_id = uuid.uuid4()
        tool_id = str(uuid.uuid4())
        db = Mock(spec=Session)

        with patch("rhesis.backend.app.services.tool.rest.jira.crud") as mock_crud:
            mock_crud.get_task.return_value = None

            with pytest.raises(ValueError, match="not found"):
                await create_jira_ticket_from_task(task_id, tool_id, db, "org", "user")

    async def test_create_jira_ticket_wrong_provider(self):
        """Raises ValueError when tool is not a Jira integration."""
        task_id = uuid.uuid4()
        tool_id = str(uuid.uuid4())
        db = Mock(spec=Session)

        mock_task = Mock()

        with (
            patch(
                "rhesis.backend.app.services.tool.rest.jira.crud"
            ) as mock_crud,
            patch(
                "rhesis.backend.app.services.tool.rest.jira.get_rest_source",
                return_value=Mock(spec=NotionSource),
            ),
        ):
            mock_crud.get_task.return_value = mock_task

            with pytest.raises(ValueError, match="not a Jira integration"):
                await create_jira_ticket_from_task(task_id, tool_id, db, "org", "user")

    async def test_create_jira_ticket_missing_space_key(self):
        """Raises ValueError when tool metadata lacks space_key."""
        task_id = uuid.uuid4()
        tool_id = str(uuid.uuid4())
        db = Mock(spec=Session)

        mock_task = Mock()
        mock_tool = Mock()
        mock_tool.tool_metadata = {}

        with (
            patch(
                "rhesis.backend.app.services.tool.rest.jira.crud"
            ) as mock_crud,
            patch(
                "rhesis.backend.app.services.tool.rest.jira.get_rest_source",
                return_value=Mock(spec=JiraRestClient),
            ),
        ):
            mock_crud.get_task.return_value = mock_task
            mock_crud.get_tool.return_value = mock_tool

            with pytest.raises(ValueError, match="not configured with a space_key"):
                await create_jira_ticket_from_task(task_id, tool_id, db, "org", "user")

    async def test_create_jira_ticket_null_metadata(self):
        """Raises ValueError when tool metadata is None."""
        task_id = uuid.uuid4()
        tool_id = str(uuid.uuid4())
        db = Mock(spec=Session)

        mock_task = Mock()
        mock_tool = Mock()
        mock_tool.tool_metadata = None

        with (
            patch(
                "rhesis.backend.app.services.tool.rest.jira.crud"
            ) as mock_crud,
            patch(
                "rhesis.backend.app.services.tool.rest.jira.get_rest_source",
                return_value=Mock(spec=JiraRestClient),
            ),
        ):
            mock_crud.get_task.return_value = mock_task
            mock_crud.get_tool.return_value = mock_tool

            with pytest.raises(ValueError, match="not configured with a space_key"):
                await create_jira_ticket_from_task(task_id, tool_id, db, "org", "user")


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestJiraRestClient:
    """Test JiraRestClient.create_issue error handling."""

    async def test_create_issue_401_raises(self):
        """401 from Jira maps to a clear ValueError."""
        import httpx
        from unittest.mock import patch as _patch

        client = JiraRestClient(
            base_url="https://test.atlassian.net",
            username="user@test.com",
            api_token="token",
        )

        mock_resp = Mock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.is_success = False
        mock_resp.text = "Unauthorized"

        with _patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(ValueError, match="authentication failed"):
                await client.create_issue("PROJ", "summary")

    async def test_create_issue_404_raises(self):
        """404 from Jira maps to a clear ValueError about the project."""
        import httpx
        from unittest.mock import patch as _patch

        client = JiraRestClient(
            base_url="https://test.atlassian.net",
            username="user@test.com",
            api_token="token",
        )

        mock_resp = Mock(spec=httpx.Response)
        mock_resp.status_code = 404
        mock_resp.is_success = False
        mock_resp.text = "Not Found"

        with _patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(ValueError, match="not found"):
                await client.create_issue("BADKEY", "summary")
