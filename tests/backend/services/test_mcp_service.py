"""
Tests for MCP service functionality in rhesis.backend.app.services.mcp_service

This module tests the MCP service including:
- Exception handling and HTTP exception mapping
- Client creation from tool ID and parameters
- Search, extract, and query operations
- Authentication testing
- Error handling and edge cases
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.mcp_service import (
    _get_mcp_client_by_tool_id,
    _get_mcp_client_from_params,
    extract_mcp,
    handle_mcp_exception,
    query_mcp,
    run_mcp_authentication_test,
    search_mcp,
)
from rhesis.sdk.services.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPConnectionError,
    MCPError,
    MCPValidationError,
)


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

    @patch("rhesis.backend.app.services.mcp_service.logger")
    def test_logs_error_for_5xx_status(self, mock_logger):
        """Test that 5xx errors are logged as errors"""
        error = MCPApplicationError(status_code=500, detail="Server error")
        handle_mcp_exception(error, "search")

        mock_logger.error.assert_called_once()
        assert "500" in str(mock_logger.error.call_args)

    @patch("rhesis.backend.app.services.mcp_service.logger")
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

    @patch("rhesis.backend.app.services.mcp_service.MCPClientFactory")
    @patch("rhesis.backend.app.services.mcp_service.crud")
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
        result = _get_mcp_client_by_tool_id(db, tool_id, org_id, user_id)

        # Assert
        assert result == mock_client
        mock_crud.get_tool.assert_called_once_with(db, uuid.UUID(tool_id), org_id, user_id)
        mock_factory.from_provider.assert_called_once_with(
            provider="notion", credentials={"NOTION_TOKEN": "test_token"}
        )
        mock_factory_instance.create_client.assert_called_once_with("notionApi")

    @patch("rhesis.backend.app.services.mcp_service.MCPClientFactory")
    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_create_client_custom_provider(self, mock_crud, mock_factory):
        """Test successfully create client for custom provider"""
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        mock_tool = Mock()
        mock_tool.tool_type.type_value = "mcp"
        mock_tool.tool_provider_type.type_value = "custom"
        mock_tool.credentials = '{"TOKEN": "test_token"}'
        mock_tool.tool_metadata = {"command": "npx", "args": ["@example/mcp-server"]}

        mock_crud.get_tool.return_value = mock_tool

        mock_factory_instance = Mock()
        mock_client = Mock()
        mock_factory_instance.create_client.return_value = mock_client
        mock_factory.from_tool_config.return_value = mock_factory_instance

        # Execute
        result = _get_mcp_client_by_tool_id(Mock(), tool_id, org_id)

        # Assert
        assert result == mock_client
        mock_factory.from_tool_config.assert_called_once_with(
            tool_name="customApi",
            tool_config={"command": "npx", "args": ["@example/mcp-server"]},
            credentials={"TOKEN": "test_token"},
        )

    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_raises_when_tool_not_found(self, mock_crud):
        """Test raises MCPConfigurationError when tool not found"""
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        mock_crud.get_tool.return_value = None

        with pytest.raises(MCPConfigurationError) as exc_info:
            _get_mcp_client_by_tool_id(Mock(), tool_id, org_id)

        assert "not found" in str(exc_info.value).lower()

    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_raises_when_tool_not_mcp_type(self, mock_crud):
        """Test raises MCPConfigurationError when tool is not MCP type"""
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        mock_tool = Mock()
        mock_tool.tool_type.type_value = "api"  # Not MCP
        mock_tool.name = "Test Tool"

        mock_crud.get_tool.return_value = mock_tool

        with pytest.raises(MCPConfigurationError) as exc_info:
            _get_mcp_client_by_tool_id(Mock(), tool_id, org_id)

        assert "not an MCP integration" in str(exc_info.value)

    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_raises_when_credentials_invalid_json(self, mock_crud):
        """Test raises MCPConfigurationError when credentials JSON is invalid"""
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        mock_tool = Mock()
        mock_tool.tool_type.type_value = "mcp"
        mock_tool.tool_provider_type.type_value = "notion"
        mock_tool.credentials = "invalid json{"

        mock_crud.get_tool.return_value = mock_tool

        with pytest.raises(MCPConfigurationError) as exc_info:
            _get_mcp_client_by_tool_id(Mock(), tool_id, org_id)

        assert "Invalid credentials format" in str(exc_info.value)

    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_raises_when_custom_provider_missing_metadata(self, mock_crud):
        """Test raises MCPConfigurationError when custom provider missing tool_metadata"""
        tool_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        mock_tool = Mock()
        mock_tool.tool_type.type_value = "mcp"
        mock_tool.tool_provider_type.type_value = "custom"
        mock_tool.credentials = '{"TOKEN": "test"}'
        mock_tool.tool_metadata = None

        mock_crud.get_tool.return_value = mock_tool

        with pytest.raises(MCPConfigurationError) as exc_info:
            _get_mcp_client_by_tool_id(Mock(), tool_id, org_id)

        assert "tool_metadata" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.services
class TestGetMCPClientFromParams:
    """Test client creation from parameters"""

    @patch("rhesis.backend.app.services.mcp_service.MCPClientFactory")
    @patch("rhesis.backend.app.services.mcp_service.crud")
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
            tool_metadata=None,
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

    @patch("rhesis.backend.app.services.mcp_service.MCPClientFactory")
    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_create_client_custom_provider(self, mock_crud, mock_factory):
        """Test successfully create client for custom provider with tool_metadata"""
        provider_type_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        credentials = {"TOKEN": "test_token"}
        tool_metadata = {"command": "npx", "args": ["@example/mcp-server"]}

        mock_provider_type = Mock()
        mock_provider_type.type_value = "custom"
        mock_crud.get_type_lookup.return_value = mock_provider_type

        mock_factory_instance = Mock()
        mock_client = Mock()
        mock_factory_instance.create_client.return_value = mock_client
        mock_factory.from_tool_config.return_value = mock_factory_instance

        # Execute
        result = _get_mcp_client_from_params(
            provider_type_id, credentials, tool_metadata, Mock(), org_id
        )

        # Assert
        assert result == mock_client
        mock_factory.from_tool_config.assert_called_once_with(
            tool_name="customApi", tool_config=tool_metadata, credentials=credentials
        )

    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_raises_when_provider_type_not_found(self, mock_crud):
        """Test raises ValueError when provider type not found"""
        provider_type_id = uuid.uuid4()
        org_id = str(uuid.uuid4())

        mock_crud.get_type_lookup.return_value = None

        with pytest.raises(ValueError) as exc_info:
            _get_mcp_client_from_params(provider_type_id, {}, None, Mock(), org_id)

        assert "not found" in str(exc_info.value).lower()

    @patch("rhesis.backend.app.services.mcp_service.crud")
    def test_raises_when_custom_provider_missing_metadata(self, mock_crud):
        """Test raises ValueError when custom provider missing tool_metadata"""
        provider_type_id = uuid.uuid4()
        org_id = str(uuid.uuid4())

        mock_provider_type = Mock()
        mock_provider_type.type_value = "custom"
        mock_crud.get_type_lookup.return_value = mock_provider_type

        with pytest.raises(ValueError) as exc_info:
            _get_mcp_client_from_params(provider_type_id, {}, None, Mock(), org_id)

        assert "tool_metadata" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestSearchMCP:
    """Test search_mcp function"""

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_search_success(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test successfully search and return list of results"""
        # Setup
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        query = "Find pages about authentication"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_model = Mock()
        mock_get_model.return_value = mock_model

        mock_client = Mock()
        mock_get_client.return_value = mock_client

        mock_template = Mock()
        mock_template.render.return_value = "Search prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.final_answer = '[{"id": "1", "url": "http://example.com", "title": "Test"}]'
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        # Execute
        result = await search_mcp(query, tool_id, db, user, org_id)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "1"
        assert result[0]["url"] == "http://example.com"
        assert result[0]["title"] == "Test"

        mock_agent_class.assert_called_once_with(
            model=mock_model,
            mcp_client=mock_client,
            system_prompt="Search prompt",
            max_iterations=10,
            verbose=False,
        )
        mock_agent.run_async.assert_called_once_with(query)

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_search_invalid_json(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test raises ValueError when agent returns invalid JSON"""
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        query = "Find pages"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()
        mock_template = Mock()
        mock_template.render.return_value = "Search prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.final_answer = "invalid json{"
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        with pytest.raises(ValueError) as exc_info:
            await search_mcp(query, tool_id, db, user, org_id)

        assert "invalid json" in str(exc_info.value).lower()

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_search_non_list_format(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test raises ValueError when agent returns non-list format"""
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        query = "Find pages"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()
        mock_template = Mock()
        mock_template.render.return_value = "Search prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.final_answer = '{"not": "a list"}'
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        with pytest.raises(ValueError) as exc_info:
            await search_mcp(query, tool_id, db, user, org_id)

        assert "expected a list" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestExtractMCP:
    """Test extract_mcp function"""

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_extract_success(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test successfully extract content and return markdown string"""
        # Setup
        item_id = "page-123"
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()

        mock_template = Mock()
        mock_template.render.return_value = "Extract prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.final_answer = "# Extracted Content\n\nThis is the content."
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        # Execute
        result = await extract_mcp(item_id, tool_id, db, user, org_id)

        # Assert
        assert result == "# Extracted Content\n\nThis is the content."
        mock_template.render.assert_called_once_with(item_id=item_id)
        mock_agent_class.assert_called_once_with(
            model=mock_get_model.return_value,
            mcp_client=mock_get_client.return_value,
            system_prompt="Extract prompt",
            max_iterations=15,
            verbose=False,
        )
        mock_agent.run_async.assert_called_once_with(f"Extract content from item {item_id}")


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestQueryMCP:
    """Test query_mcp function"""

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_query_with_default_prompt(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test successfully execute query with default prompt"""
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        query = "Create a page"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()

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
        mock_agent_class.return_value = mock_agent

        # Execute
        result = await query_mcp(query, tool_id, db, user, org_id)

        # Assert
        assert isinstance(result, dict)
        assert result["final_answer"] == "Page created"
        assert result["success"] is True
        mock_template.render.assert_called_once()
        mock_agent_class.assert_called_once_with(
            model=mock_get_model.return_value,
            mcp_client=mock_get_client.return_value,
            system_prompt="Default query prompt",
            max_iterations=10,
            verbose=False,
        )

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    async def test_query_with_custom_prompt(
        self, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test successfully execute query with custom system_prompt"""
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        query = "Create a page"
        custom_prompt = "Custom system prompt"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.model_dump.return_value = {"final_answer": "Done"}
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        # Execute
        result = await query_mcp(query, tool_id, db, user, org_id, system_prompt=custom_prompt)

        # Assert
        mock_agent_class.assert_called_once_with(
            model=mock_get_model.return_value,
            mcp_client=mock_get_client.return_value,
            system_prompt=custom_prompt,
            max_iterations=10,
            verbose=False,
        )

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_query_with_custom_max_iterations(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test successfully execute query with custom max_iterations"""
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        query = "Create a page"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()

        mock_template = Mock()
        mock_template.render.return_value = "Default query prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.model_dump.return_value = {"final_answer": "Done"}
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        # Execute
        result = await query_mcp(query, tool_id, db, user, org_id, max_iterations=20)

        # Assert
        mock_agent_class.assert_called_once_with(
            model=mock_get_model.return_value,
            mcp_client=mock_get_client.return_value,
            system_prompt="Default query prompt",
            max_iterations=20,
            verbose=False,
        )


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestTestMCPAuthentication:
    """Test run_mcp_authentication_test function"""

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_authentication_with_tool_id(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test successfully test authentication using tool_id"""
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()

        mock_template = Mock()
        mock_template.render.return_value = "Auth test prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.final_answer = '{"is_authenticated": "Yes", "message": "Auth successful"}'
        mock_result.success = True
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        # Execute
        result = await run_mcp_authentication_test(db, user, org_id, tool_id=tool_id)

        # Assert
        assert isinstance(result, dict)
        assert result["is_authenticated"] == "Yes"
        assert result["message"] == "Auth successful"
        mock_get_client.assert_called_once_with(db, tool_id, org_id, None)
        mock_agent_class.assert_called_once_with(
            model=mock_get_model.return_value,
            mcp_client=mock_get_client.return_value,
            system_prompt="Auth test prompt",
            max_iterations=5,
            verbose=False,
        )

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_from_params")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_authentication_with_params(
        self, mock_jinja_env, mock_get_model, mock_get_client_from_params, mock_agent_class
    ):
        """Test successfully test authentication using provider_type_id and credentials"""
        provider_type_id = uuid.uuid4()
        credentials = {"NOTION_TOKEN": "test_token"}
        org_id = "test-org-id"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client_from_params.return_value = Mock()

        mock_template = Mock()
        mock_template.render.return_value = "Auth test prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.final_answer = '{"is_authenticated": "No", "message": "Auth failed"}'
        mock_result.success = True
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        # Execute
        result = await run_mcp_authentication_test(
            db, user, org_id, provider_type_id=provider_type_id, credentials=credentials
        )

        # Assert
        assert isinstance(result, dict)
        assert result["is_authenticated"] == "No"
        mock_get_client_from_params.assert_called_once_with(
            provider_type_id=provider_type_id,
            credentials=credentials,
            tool_metadata=None,
            db=db,
            organization_id=org_id,
            user_id=None,
        )

    @patch("rhesis.backend.app.services.mcp_service.MCPAgent")
    @patch("rhesis.backend.app.services.mcp_service._get_mcp_client_by_tool_id")
    @patch("rhesis.backend.app.services.mcp_service.get_user_generation_model")
    @patch("rhesis.backend.app.services.mcp_service.jinja_env")
    async def test_authentication_failure(
        self, mock_jinja_env, mock_get_model, mock_get_client, mock_agent_class
    ):
        """Test raises ValueError when agent.run_async fails"""
        tool_id = "test-tool-id"
        org_id = "test-org-id"
        db = Mock(spec=Session)
        user = Mock(spec=User)

        mock_get_model.return_value = Mock()
        mock_get_client.return_value = Mock()
        mock_template = Mock()
        mock_template.render.return_value = "Auth test prompt"
        mock_jinja_env.get_template.return_value = mock_template

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.error = "Agent failed"
        mock_agent.run_async = AsyncMock(return_value=mock_result)
        mock_agent_class.return_value = mock_agent

        with pytest.raises(ValueError) as exc_info:
            await run_mcp_authentication_test(db, user, org_id, tool_id=tool_id)

        assert "Authentication test failed" in str(exc_info.value)
