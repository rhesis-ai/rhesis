"""
Tests for MCP service functionality in rhesis.backend.app.services.mcp

This module tests the MCP service including:
- Exception handling and HTTP exception mapping
- Client creation from tool ID and parameters
- Search, extract, and query operations
- Error handling and edge cases
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.services.tool.mcp import (
    _get_mcp_client_from_params,
    _get_mcp_tool_config,
    handle_mcp_exception,
    query_mcp,
)
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.sdk.agents.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPConnectionError,
    MCPError,
    MCPValidationError,
)
from rhesis.sdk.context import EndpointContext


def _make_ctx(org_id="test-org-id", user_id="test-user-id", db=None):
    """Build an EndpointContext for tests, optionally with a db factory stub."""
    if db is not None:

        class _FakeCtxMgr:
            def __enter__(self_):
                return db

            def __exit__(self_, *args):
                pass

        return EndpointContext(
            organization_id=org_id,
            user_id=user_id,
            _db_factory=lambda o, u: _FakeCtxMgr(),
        )
    return EndpointContext(organization_id=org_id, user_id=user_id)


@pytest.mark.unit
@pytest.mark.services
class TestHandleMCPException:
    """Test exception handling and HTTP exception mapping"""

    def test_handle_mcp_application_error_with_detail(self):
        """Test MCPApplicationError uses detail attribute"""
        error = MCPApplicationError(status_code=404, detail="Resource not found")
        result = handle_mcp_exception(error, "search")

        assert isinstance(result, HTTPException)
        assert result.status_code == 404
        assert result.detail == "Resource not found"

    def test_handle_mcp_application_error_auth_401_maps_to_502(self):
        """Test authentication errors (401) map to 502 Bad Gateway"""
        error = MCPApplicationError(
            status_code=401, detail="Unauthorized", original_error=Exception("Auth failed")
        )
        result = handle_mcp_exception(error, "search")

        assert isinstance(result, HTTPException)
        assert result.status_code == 502
        assert "MCP tool authentication failed" in result.detail

    def test_handle_mcp_application_error_auth_403_maps_to_502(self):
        """Test authentication errors (403) map to 502 Bad Gateway"""
        error = MCPApplicationError(
            status_code=403, detail="Forbidden", original_error=Exception("Forbidden")
        )
        result = handle_mcp_exception(error, "extract")

        assert isinstance(result, HTTPException)
        assert result.status_code == 502
        assert "MCP tool authentication failed" in result.detail

    def test_handle_mcp_configuration_error(self):
        """Test MCPConfigurationError maps to 404"""
        error = MCPConfigurationError("Tool not found")
        result = handle_mcp_exception(error, "query")

        assert isinstance(result, HTTPException)
        assert result.status_code == 404
        assert "Tool not found" in result.detail

    def test_handle_mcp_connection_error(self):
        """Test MCPConnectionError maps to 503"""
        error = MCPConnectionError("Connection failed")
        result = handle_mcp_exception(error, "search")

        assert isinstance(result, HTTPException)
        assert result.status_code == 503
        assert "Connection failed" in result.detail

    def test_handle_mcp_validation_error(self):
        """Test MCPValidationError maps to 422"""
        error = MCPValidationError("Invalid input")
        result = handle_mcp_exception(error, "extract")

        assert isinstance(result, HTTPException)
        assert result.status_code == 422
        assert "Invalid input" in result.detail

    def test_handle_mcp_error_with_status_code(self):
        """Test generic MCPError with status code"""
        error = MCPError("Generic error", category="application", status_code=500)
        result = handle_mcp_exception(error, "query")

        assert isinstance(result, HTTPException)
        assert result.status_code == 500

    def test_handle_mcp_error_without_status_code_defaults_to_500(self):
        """Test MCPError without status code defaults to 500"""
        error = MCPError("Generic error", category="application", status_code=None)
        result = handle_mcp_exception(error, "search")

        assert isinstance(result, HTTPException)
        assert result.status_code == 500

    def test_handle_non_mcp_exception(self):
        """Test non-MCP exceptions map to generic 500"""
        error = ValueError("Unexpected error")
        result = handle_mcp_exception(error, "extract")

        assert isinstance(result, HTTPException)
        assert result.status_code == 500
        assert "unexpected error occurred" in result.detail.lower()

    @patch("rhesis.backend.app.services.tool.mcp.exceptions.logger")
    def test_logs_error_for_5xx_status(self, mock_logger):
        """Test that 5xx errors are logged as errors"""
        error = MCPApplicationError(status_code=500, detail="Server error")
        handle_mcp_exception(error, "search")

        mock_logger.error.assert_called_once()
        assert "500" in str(mock_logger.error.call_args)

    @patch("rhesis.backend.app.services.tool.mcp.exceptions.logger")
    def test_logs_warning_for_4xx_status(self, mock_logger):
        """Test that 4xx errors are logged as warnings"""
        error = MCPApplicationError(status_code=404, detail="Not found")
        handle_mcp_exception(error, "query")

        mock_logger.warning.assert_called_once()
        assert "404" in str(mock_logger.warning.call_args)

    def test_handle_mcp_error_preserves_original_error_info(self):
        """Test that original error information is preserved in logs"""
        original = ValueError("Original error")
        error = MCPError("Wrapped error", category="config", original_error=original)
        result = handle_mcp_exception(error, "search")

        assert isinstance(result, HTTPException)
        # Original error should be accessible for logging
        assert error.original_error == original


@pytest.mark.unit
@pytest.mark.services
class TestGetMCPClientByToolId:
    """Test client creation from tool ID"""

    @patch("rhesis.backend.app.services.tool.mcp.config.MCPClientFactory")
    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    def test_create_client_standard_provider(self, mock_crud, mock_factory):
        """Test successfully create client for standard provider"""
        # Setup mocks
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_tool = Mock()
        mock_tool.tool_type.type_value = "mcp"
        mock_tool.tool_provider_type.type_value = "notion"
        mock_tool.credentials = '{"NOTION_TOKEN": "test_token"}'
        mock_tool.tool_metadata = None

        mock_crud.get_tool.return_value = mock_tool

        mock_factory_instance = Mock()
        mock_client = Mock()
        mock_factory_instance.create_client.return_value = mock_client
        mock_factory.from_provider.return_value = mock_factory_instance

        # Execute
        db = Mock()
        result, provider_name = _get_mcp_tool_config(db, tool_id, org_id, user_id)

        # Assert
        assert result == mock_client
        assert provider_name == "notion"
        mock_crud.get_tool.assert_called_once_with(db, uuid.UUID(tool_id), org_id, user_id)
        mock_factory.from_provider.assert_called_once_with(
            provider="notion", credentials={"NOTION_TOKEN": "test_token"}
        )
        mock_factory_instance.create_client.assert_called_once_with("notion")

    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    def test_raises_when_tool_not_found(self, mock_crud):
        """Test raises ToolConfigurationError when tool not found"""
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        mock_crud.get_tool.return_value = None

        with pytest.raises(ToolConfigurationError) as exc_info:
            _get_mcp_tool_config(Mock(), tool_id, org_id)

        assert "not found" in str(exc_info.value).lower()

    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    def test_raises_when_credentials_invalid_json(self, mock_crud):
        """Test raises ToolConfigurationError when credentials JSON is invalid"""
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        mock_tool = Mock()
        mock_tool.tool_type.type_value = "mcp"
        mock_tool.tool_provider_type.type_value = "notion"
        mock_tool.credentials = "invalid json{"

        mock_crud.get_tool.return_value = mock_tool

        with pytest.raises(ToolConfigurationError) as exc_info:
            _get_mcp_tool_config(Mock(), tool_id, org_id)

        assert "Invalid credentials format" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.services
class TestGetMCPClientFromParams:
    """Test client creation from parameters"""

    @patch("rhesis.backend.app.services.tool.mcp.config.MCPClientFactory")
    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    def test_create_client_standard_provider(self, mock_crud, mock_factory):
        """Test successfully create client for standard provider"""
        provider_type_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        credentials = {"NOTION_TOKEN": "test_token"}

        mock_provider_type = Mock()
        mock_provider_type.type_value = "notion"
        mock_crud.get_type_lookup.return_value = mock_provider_type

        mock_factory_instance = Mock()
        mock_client = Mock()
        mock_factory_instance.create_client.return_value = mock_client
        mock_factory.from_provider.return_value = mock_factory_instance

        # Execute
        db = Mock()
        result = _get_mcp_client_from_params(
            provider_type_id=provider_type_id,
            credentials=credentials,
            db=db,
            organization_id=org_id,
            user_id=None,
        )

        # Assert
        assert result == mock_client
        mock_crud.get_type_lookup.assert_called_once_with(db, provider_type_id, org_id, None)
        mock_factory.from_provider.assert_called_once_with(
            provider="notion", credentials=credentials
        )

    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    def test_raises_when_provider_type_not_found(self, mock_crud):
        """Test raises ValueError when provider type not found"""
        provider_type_id = uuid.uuid4()
        org_id = str(uuid.uuid4())

        mock_crud.get_type_lookup.return_value = None

        with pytest.raises(ValueError) as exc_info:
            _get_mcp_client_from_params(provider_type_id, {}, Mock(), org_id)

        assert "not found" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestQueryMCP:
    """Test query_mcp function"""

    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    @patch("rhesis.backend.app.services.tool.mcp.operations.get_agent_event_handlers",
           return_value=[])
    @patch("rhesis.backend.app.services.tool.mcp.operations.MCPAgent")
    @patch("rhesis.backend.app.services.tool.mcp.operations._get_mcp_tool_config")
    @patch("rhesis.backend.app.services.tool.mcp.operations.jinja_env")
    async def test_query_with_default_prompt(
        self, mock_jinja_env, mock_get_client, mock_mcp_agent, mock_get_handlers, mock_crud
    ):
        """Test successfully execute query with default prompt"""
        tool_id = "test-tool-id"
        query = "Create a page"
        db = Mock(spec=Session)
        ctx = _make_ctx(db=db)

        mock_client = Mock()
        mock_get_client.return_value = (mock_client, "notion")

        mock_template = Mock()
        mock_template.render.return_value = "Default query prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.model_dump.return_value = {
            "final_answer": "Page created",
            "success": True,
            "iterations_used": 2,
        }
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_mcp_agent.return_value = mock_agent

        # Execute
        result = await query_mcp(query, tool_id, ctx)

        # Assert
        assert isinstance(result, dict)
        assert result["final_answer"] == "Page created"
        assert result["success"] is True
        mock_template.render.assert_called_once()
        mock_mcp_agent.assert_called_once_with(
            model=get_model_settings().generation_model,
            mcp_client=mock_client,
            system_prompt="Default query prompt",
            max_iterations=10,
            verbose=False,
            event_handlers=[],
        )

    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    @patch("rhesis.backend.app.services.tool.mcp.operations.get_agent_event_handlers",
           return_value=[])
    @patch("rhesis.backend.app.services.tool.mcp.operations.MCPAgent")
    @patch("rhesis.backend.app.services.tool.mcp.operations._get_mcp_tool_config")
    async def test_query_with_custom_prompt(
        self, mock_get_client, mock_mcp_agent, mock_get_handlers, mock_crud
    ):
        """Test successfully execute query with custom system_prompt"""
        tool_id = "test-tool-id"
        query = "Create a page"
        custom_prompt = "Custom system prompt"
        db = Mock(spec=Session)
        ctx = _make_ctx(db=db)

        mock_client = Mock()
        mock_get_client.return_value = (mock_client, "notion")

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.model_dump.return_value = {"final_answer": "Done"}
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_mcp_agent.return_value = mock_agent

        # Execute
        await query_mcp(
            query,
            tool_id,
            ctx,
            system_prompt=custom_prompt,
        )

        # Assert
        mock_mcp_agent.assert_called_once_with(
            model=get_model_settings().generation_model,
            mcp_client=mock_client,
            system_prompt=custom_prompt,
            max_iterations=10,
            verbose=False,
            event_handlers=[],
        )

    @patch("rhesis.backend.app.services.tool.mcp.config.crud")
    @patch("rhesis.backend.app.services.tool.mcp.operations.get_agent_event_handlers",
           return_value=[])
    @patch("rhesis.backend.app.services.tool.mcp.operations.MCPAgent")
    @patch("rhesis.backend.app.services.tool.mcp.operations._get_mcp_tool_config")
    @patch("rhesis.backend.app.services.tool.mcp.operations.jinja_env")
    async def test_query_with_custom_max_iterations(
        self, mock_jinja_env, mock_get_client, mock_mcp_agent, mock_get_handlers, mock_crud
    ):
        """Test successfully execute query with custom max_iterations"""
        tool_id = "test-tool-id"
        query = "Create a page"
        db = Mock(spec=Session)
        ctx = _make_ctx(db=db)

        mock_client = Mock()
        mock_get_client.return_value = (mock_client, "notion")

        mock_template = Mock()
        mock_template.render.return_value = "Default query prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.model_dump.return_value = {"final_answer": "Done"}
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_mcp_agent.return_value = mock_agent

        # Execute
        await query_mcp(
            query,
            tool_id,
            ctx,
            max_iterations=20,
        )

        # Assert
        mock_mcp_agent.assert_called_once_with(
            model=get_model_settings().generation_model,
            mcp_client=mock_client,
            system_prompt="Default query prompt",
            max_iterations=20,
            verbose=False,
            event_handlers=[],
        )
