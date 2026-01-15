"""Tests for ToolExecutor class."""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from rhesis.sdk.services.mcp.exceptions import MCPApplicationError, MCPConnectionError
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.schemas import ToolCall, ToolResult


@pytest.mark.unit
class TestToolExecutor:
    """Test ToolExecutor class"""

    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client"""
        client = Mock()
        client.list_tools = AsyncMock(return_value=[])
        client.call_tool = AsyncMock()
        return client

    @pytest.fixture
    def executor(self, mock_mcp_client):
        """Create ToolExecutor instance"""
        return ToolExecutor(mock_mcp_client)

    @pytest.mark.asyncio
    async def test_get_available_tools(self, executor, mock_mcp_client):
        """Test getting available tools"""
        tools = [{"name": "tool1", "description": "Test tool"}]
        mock_mcp_client.list_tools.return_value = tools

        result = await executor.get_available_tools()

        assert result == tools
        mock_mcp_client.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, executor, mock_mcp_client):
        """Test successful tool execution"""
        tool_call = ToolCall(tool_name="search_pages", arguments='{"query": "test"}')

        # Mock MCP result
        mock_result = Mock()
        mock_result.isError = False
        mock_content = Mock()
        mock_content.text = "Found 5 pages"
        mock_result.content = [mock_content]

        mock_mcp_client.call_tool.return_value = mock_result

        result = await executor.execute_tool(tool_call)

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.tool_name == "search_pages"
        assert "Found 5 pages" in result.content
        mock_mcp_client.call_tool.assert_called_once_with("search_pages", {"query": "test"})

    @pytest.mark.asyncio
    async def test_execute_tool_transport_error(self, executor, mock_mcp_client):
        """Test tool execution with transport error"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = True
        mock_content = Mock()
        mock_content.text = "Transport error"
        mock_result.content = [mock_content]

        mock_mcp_client.call_tool.return_value = mock_result

        result = await executor.execute_tool(tool_call)

        assert result.success is False
        assert result.error == "Transport error"

    @pytest.mark.asyncio
    async def test_execute_tool_fatal_application_error(self, executor, mock_mcp_client):
        """Test tool execution with fatal application error (5xx)"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = False
        mock_content = Mock()
        # Simulate 500 error in JSON response
        mock_content.text = json.dumps({"status": 500, "message": "Server error"})
        mock_result.content = [mock_content]

        mock_mcp_client.call_tool.return_value = mock_result

        with pytest.raises(MCPApplicationError) as exc_info:
            await executor.execute_tool(tool_call)

        assert exc_info.value.status_code == 500
        assert "Server error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_execute_tool_fatal_auth_error_401(self, executor, mock_mcp_client):
        """Test tool execution with fatal auth error (401)"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = False
        mock_content = Mock()
        mock_content.text = json.dumps({"status": 401, "message": "Unauthorized"})
        mock_result.content = [mock_content]

        mock_mcp_client.call_tool.return_value = mock_result

        with pytest.raises(MCPApplicationError) as exc_info:
            await executor.execute_tool(tool_call)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_execute_tool_recoverable_error(self, executor, mock_mcp_client):
        """Test tool execution with recoverable error (4xx, not 401/403/404)"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = False
        mock_content = Mock()
        # 400 Bad Request is recoverable
        mock_content.text = json.dumps({"status": 400, "message": "Bad request"})
        mock_result.content = [mock_content]

        mock_mcp_client.call_tool.return_value = mock_result

        result = await executor.execute_tool(tool_call)

        assert result.success is False
        assert "400" in result.error
        assert "Bad request" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_connection_error(self, executor, mock_mcp_client):
        """Test tool execution with connection error"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_mcp_client.call_tool.side_effect = ConnectionError("Connection failed")

        with pytest.raises(MCPConnectionError) as exc_info:
            await executor.execute_tool(tool_call)

        assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_tool_timeout_error(self, executor, mock_mcp_client):
        """Test tool execution with timeout error"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_mcp_client.call_tool.side_effect = TimeoutError("Request timeout")

        with pytest.raises(MCPConnectionError) as exc_info:
            await executor.execute_tool(tool_call)

        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_runtime_error_not_connected(self, executor, mock_mcp_client):
        """Test tool execution with RuntimeError for not connected"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_mcp_client.call_tool.side_effect = RuntimeError("Not connected to MCP server")

        with pytest.raises(MCPConnectionError) as exc_info:
            await executor.execute_tool(tool_call)

        assert "connection" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_runtime_error_other(self, executor, mock_mcp_client):
        """Test tool execution with other RuntimeError"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_mcp_client.call_tool.side_effect = RuntimeError("Other runtime error")

        result = await executor.execute_tool(tool_call)

        assert result.success is False
        assert "Other runtime error" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_unexpected_error(self, executor, mock_mcp_client):
        """Test tool execution with unexpected error"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_mcp_client.call_tool.side_effect = ValueError("Unexpected error")

        result = await executor.execute_tool(tool_call)

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_empty_content(self, executor, mock_mcp_client):
        """Test tool execution with empty content"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = False
        mock_result.content = []

        mock_mcp_client.call_tool.return_value = mock_result

        result = await executor.execute_tool(tool_call)

        assert result.success is True
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_execute_tool_multiple_content_items(self, executor, mock_mcp_client):
        """Test tool execution with multiple content items"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = False
        mock_content1 = Mock()
        mock_content1.text = "First part"
        mock_content2 = Mock()
        mock_content2.text = "Second part"
        mock_result.content = [mock_content1, mock_content2]

        mock_mcp_client.call_tool.return_value = mock_result

        result = await executor.execute_tool(tool_call)

        assert result.success is True
        assert "First part" in result.content
        assert "Second part" in result.content

    @pytest.mark.asyncio
    async def test_execute_tool_json_error_with_status_code_field(self, executor, mock_mcp_client):
        """Test parsing error with status_code field instead of status (404 is recoverable)"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = False
        mock_content = Mock()
        mock_content.text = json.dumps({"status_code": 404, "detail": "Not found"})
        mock_result.content = [mock_content]

        mock_mcp_client.call_tool.return_value = mock_result

        # 404 is recoverable, so it returns ToolResult with success=False
        result = await executor.execute_tool(tool_call)

        assert result.success is False
        assert "404" in result.error
        assert "Not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_json_error_with_message_field(self, executor, mock_mcp_client):
        """Test parsing error with message field"""
        tool_call = ToolCall(tool_name="test_tool", arguments="{}")

        mock_result = Mock()
        mock_result.isError = False
        mock_content = Mock()
        mock_content.text = json.dumps({"status": 500, "message": "Server error"})
        mock_result.content = [mock_content]

        mock_mcp_client.call_tool.return_value = mock_result

        with pytest.raises(MCPApplicationError) as exc_info:
            await executor.execute_tool(tool_call)

        assert "Server error" in exc_info.value.detail
