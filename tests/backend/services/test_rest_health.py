"""Tests for run_rest_health_check — the tool test-connection entry point."""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.tool.rest.health import run_rest_health_check
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp.exceptions import MCPConfigurationError

_OK = {"is_authenticated": "Yes", "message": "Connected"}


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestRunRestHealthCheck:
    """Test both the tool_id path and the provider_type_id + credentials path."""

    async def test_existing_tool_path(self):
        db = Mock(spec=Session)
        tool = Mock()
        tool.tool_provider_type.type_value = "notion"
        tool.credentials = '{"NOTION_TOKEN": "tok"}'

        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value=_OK)

        with (
            patch("rhesis.backend.app.services.tool.rest.health.crud") as mock_crud,
            patch(
                "rhesis.backend.app.services.tool.rest.health.build_client",
                return_value=mock_client,
            ) as mock_build,
        ):
            mock_crud.get_tool.return_value = tool
            result = await run_rest_health_check(
                db, "org", tool_id=str(uuid.uuid4()), user_id="user"
            )

        assert result == _OK
        assert mock_build.call_args[0][0] == "notion"

    async def test_unsaved_provider_path(self):
        db = Mock(spec=Session)
        provider_type = Mock()
        provider_type.type_value = "github"

        mock_client = Mock()
        mock_client.health_check = AsyncMock(return_value=_OK)

        with (
            patch("rhesis.backend.app.services.tool.rest.health.crud") as mock_crud,
            patch(
                "rhesis.backend.app.services.tool.rest.health.build_client",
                return_value=mock_client,
            ) as mock_build,
        ):
            mock_crud.get_type_lookup.return_value = provider_type
            result = await run_rest_health_check(
                db,
                "org",
                provider_type_id=uuid.uuid4(),
                credentials={"GITHUB_PERSONAL_ACCESS_TOKEN": "tok"},
            )

        assert result == _OK
        assert mock_build.call_args[0][0] == "github"

    async def test_tool_not_found_raises(self):
        db = Mock(spec=Session)
        with patch("rhesis.backend.app.services.tool.rest.health.crud") as mock_crud:
            mock_crud.get_tool.return_value = None
            with pytest.raises(MCPConfigurationError, match="not found"):
                await run_rest_health_check(db, "org", tool_id=str(uuid.uuid4()))

    async def test_deleted_tool_raises(self):
        db = Mock(spec=Session)
        with patch("rhesis.backend.app.services.tool.rest.health.crud") as mock_crud:
            mock_crud.get_tool.side_effect = ItemDeletedException("Tool", "gone")
            with pytest.raises(MCPConfigurationError, match="has been deleted"):
                await run_rest_health_check(db, "org", tool_id=str(uuid.uuid4()))

    async def test_unknown_provider_type_raises(self):
        db = Mock(spec=Session)
        with patch("rhesis.backend.app.services.tool.rest.health.crud") as mock_crud:
            mock_crud.get_type_lookup.return_value = None
            with pytest.raises(MCPConfigurationError, match="not found"):
                await run_rest_health_check(
                    db, "org", provider_type_id=uuid.uuid4(), credentials={}
                )
