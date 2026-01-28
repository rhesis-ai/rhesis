"""Tests for MCPClient and MCPClientFactory classes."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from rhesis.sdk.services.mcp.client import MCPClient, MCPClientFactory


@pytest.mark.unit
class TestMCPClient:
    """Test MCPClient class"""

    def test_client_initialization_stdio(self):
        """Test client initialization with stdio transport"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": ["@test/mcp-server"], "env": {}},
        )

        assert client.server_name == "test_server"
        assert client.transport_type == "stdio"
        assert client.transport_params["command"] == "npx"
        assert client.session is None

    def test_client_initialization_http(self):
        """Test client initialization with HTTP transport"""
        client = MCPClient(
            server_name="test_server",
            transport_type="http",
            transport_params={"url": "https://api.example.com", "headers": {}},
        )

        assert client.transport_type == "http"
        assert client.transport_params["url"] == "https://api.example.com"

    def test_client_initialization_sse(self):
        """Test client initialization with SSE transport"""
        client = MCPClient(
            server_name="test_server",
            transport_type="sse",
            transport_params={"url": "https://api.example.com/sse", "headers": {}},
        )

        assert client.transport_type == "sse"

    @pytest.mark.asyncio
    async def test_connect_stdio(self):
        """Test connecting via stdio transport"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={
                "command": "npx",
                "args": ["@test/mcp-server"],
                "env": {"TOKEN": "test"},
            },
        )

        mock_context = AsyncMock()
        mock_read = Mock()
        mock_write = Mock()
        mock_context.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock()
        mock_session.initialize = AsyncMock()

        with patch("rhesis.sdk.services.mcp.client.stdio_client", return_value=mock_context):
            with patch("rhesis.sdk.services.mcp.client.ClientSession", return_value=mock_session):
                await client.connect()

        assert client.session == mock_session
        mock_session.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_http(self):
        """Test connecting via HTTP transport"""
        client = MCPClient(
            server_name="test_server",
            transport_type="http",
            transport_params={"url": "https://api.example.com", "headers": {}},
        )

        mock_context = AsyncMock()
        mock_read = Mock()
        mock_write = Mock()
        mock_get_session_id = Mock()
        mock_context.__aenter__ = AsyncMock(
            return_value=(mock_read, mock_write, mock_get_session_id)
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock()
        mock_session.initialize = AsyncMock()

        # Mock httpx.AsyncClient to prevent real HTTP requests
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("rhesis.sdk.services.mcp.client.httpx.AsyncClient", return_value=mock_client):
            with patch(
                "rhesis.sdk.services.mcp.client.streamablehttp_client", return_value=mock_context
            ):
                with patch(
                    "rhesis.sdk.services.mcp.client.ClientSession", return_value=mock_session
                ):
                    await client.connect()

        assert client.session == mock_session

    @pytest.mark.asyncio
    async def test_connect_sse(self):
        """Test connecting via SSE transport"""
        client = MCPClient(
            server_name="test_server",
            transport_type="sse",
            transport_params={"url": "https://api.example.com/sse", "headers": {}},
        )

        mock_context = AsyncMock()
        mock_read = Mock()
        mock_write = Mock()
        mock_context.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock()
        mock_session.initialize = AsyncMock()

        # Mock httpx.AsyncClient to prevent real HTTP requests
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("rhesis.sdk.services.mcp.client.httpx.AsyncClient", return_value=mock_client):
            with patch("rhesis.sdk.services.mcp.client.sse_client", return_value=mock_context):
                with patch(
                    "rhesis.sdk.services.mcp.client.ClientSession", return_value=mock_session
                ):
                    await client.connect()

        assert client.session == mock_session

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting from MCP server"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": [], "env": {}},
        )

        mock_session = AsyncMock()
        mock_context = AsyncMock()
        client.session = mock_session
        client._transport_context = mock_context

        await client.disconnect()

        mock_session.__aexit__.assert_called_once()
        mock_context.__aexit__.assert_called_once()
        assert client.session is None

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing available tools"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": [], "env": {}},
        )

        mock_session = AsyncMock()
        mock_tool = Mock()
        mock_tool.name = "search_pages"
        mock_tool.description = "Search pages"
        mock_tool.inputSchema = {"type": "object"}
        mock_result = Mock()
        mock_result.tools = [mock_tool]
        mock_session.list_tools = AsyncMock(return_value=mock_result)

        client.session = mock_session

        tools = await client.list_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "search_pages"
        assert tools[0]["description"] == "Search pages"

    @pytest.mark.asyncio
    async def test_list_tools_not_connected(self):
        """Test listing tools when not connected raises RuntimeError"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": [], "env": {}},
        )

        with pytest.raises(RuntimeError) as exc_info:
            await client.list_tools()

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test calling a tool"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": [], "env": {}},
        )

        mock_session = AsyncMock()
        mock_result = Mock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        client.session = mock_session

        result = await client.call_tool("search_pages", {"query": "test"})

        assert result == mock_result
        mock_session.call_tool.assert_called_once_with("search_pages", {"query": "test"})

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self):
        """Test calling tool when not connected raises RuntimeError"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": [], "env": {}},
        )

        with pytest.raises(RuntimeError) as exc_info:
            await client.call_tool("test_tool", {})

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_resources(self):
        """Test listing resources"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": [], "env": {}},
        )

        mock_session = AsyncMock()
        mock_resource = Mock()
        mock_resource.uri = "resource://test"
        mock_resource.name = "Test Resource"
        mock_resource.description = "A test resource"
        mock_resource.mimeType = "text/plain"
        mock_result = Mock()
        mock_result.resources = [mock_resource]
        mock_session.list_resources = AsyncMock(return_value=mock_result)

        client.session = mock_session

        resources = await client.list_resources()

        assert len(resources) == 1
        assert resources[0]["uri"] == "resource://test"
        assert resources[0]["name"] == "Test Resource"

    @pytest.mark.asyncio
    async def test_read_resource(self):
        """Test reading a resource"""
        client = MCPClient(
            server_name="test_server",
            transport_type="stdio",
            transport_params={"command": "npx", "args": [], "env": {}},
        )

        mock_session = AsyncMock()
        mock_content = Mock()
        mock_content.text = "Resource content"
        mock_result = Mock()
        mock_result.contents = [mock_content]
        mock_session.read_resource = AsyncMock(return_value=mock_result)

        client.session = mock_session

        content = await client.read_resource("resource://test")

        assert content == "Resource content"


@pytest.mark.unit
class TestMCPClientFactory:
    """Test MCPClientFactory class"""

    def test_factory_init_with_config_path(self):
        """Test factory initialization with config path"""
        factory = MCPClientFactory(config_path="/path/to/config.json")

        assert factory.config_path == "/path/to/config.json"
        assert factory.config_dict is None

    def test_factory_init_with_config_dict(self):
        """Test factory initialization with config dict"""
        config = {"mcpServers": {"test": {"command": "npx", "args": []}}}
        factory = MCPClientFactory(config_dict=config)

        assert factory.config_dict == config
        assert factory.config_path is None

    def test_factory_init_without_config_raises(self):
        """Test factory initialization without config raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            MCPClientFactory()

        assert "must be provided" in str(exc_info.value)

    def test_load_config_from_dict(self):
        """Test loading config from dict"""
        config = {"mcpServers": {"test": {"command": "npx"}}}
        factory = MCPClientFactory(config_dict=config)

        loaded = factory._load_config()

        assert loaded == config

    @patch("pathlib.Path.exists")
    @patch("builtins.open", create=True)
    def test_load_config_from_file(self, mock_open, mock_exists):
        """Test loading config from file"""
        config_content = {"mcpServers": {"test": {"command": "npx"}}}
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps(config_content)
        mock_open.return_value = mock_file
        mock_exists.return_value = True

        factory = MCPClientFactory(config_path="/path/to/config.json")

        loaded = factory._load_config()

        assert loaded == config_content
        mock_open.assert_called_once()

    @patch("builtins.open", create=True)
    def test_load_config_file_not_found(self, mock_open):
        """Test loading config from non-existent file raises FileNotFoundError"""
        mock_open.side_effect = FileNotFoundError()

        factory = MCPClientFactory(config_path="/nonexistent/config.json")

        with pytest.raises(FileNotFoundError):
            factory._load_config()

    def test_create_client(self):
        """Test creating client from factory"""
        config = {
            "mcpServers": {
                "test_server": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["@test/mcp-server"],
                    "env": {},
                }
            }
        }
        factory = MCPClientFactory(config_dict=config)

        client = factory.create_client("test_server")

        assert isinstance(client, MCPClient)
        assert client.server_name == "test_server"
        assert client.transport_type == "stdio"

    def test_create_client_server_not_found(self):
        """Test creating client with non-existent server raises ValueError"""
        config = {"mcpServers": {"test": {"command": "npx"}}}
        factory = MCPClientFactory(config_dict=config)

        with pytest.raises(ValueError) as exc_info:
            factory.create_client("nonexistent")

        assert "not found" in str(exc_info.value).lower()

    def test_create_client_invalid_config(self):
        """Test creating client with invalid config raises ValueError"""
        config = {}  # Missing mcpServers
        factory = MCPClientFactory(config_dict=config)

        with pytest.raises(ValueError) as exc_info:
            factory.create_client("test")

        assert (
            "mcpservers" in str(exc_info.value).lower() or "servers" in str(exc_info.value).lower()
        )

    @patch("rhesis.sdk.services.mcp.client.Path")
    def test_from_provider(self, mock_path):
        """Test creating factory from provider name"""
        mock_template_file = Mock()
        mock_template_file.exists.return_value = True
        mock_template_file.read_text.return_value = (
            '{"mcpServers": {"notion": {"command": "npx", '
            '"args": ["-y", "@notionhq/notion-mcp-server"], '
            '"env": {"NOTION_TOKEN": "{{ NOTION_TOKEN }}"}}}}'
        )

        mock_templates_dir = Mock()
        mock_templates_dir.__truediv__ = Mock(return_value=mock_template_file)
        mock_path.return_value.parent.__truediv__ = Mock(return_value=mock_templates_dir)

        credentials = {"NOTION_TOKEN": "ntn_test123"}

        factory = MCPClientFactory.from_provider("notion", credentials)

        assert isinstance(factory, MCPClientFactory)
        assert factory.config_dict is not None
        assert "mcpServers" in factory.config_dict

    @patch("rhesis.sdk.services.mcp.client.Path")
    def test_from_provider_not_supported(self, mock_path):
        """Test creating factory from unsupported provider raises ValueError"""
        mock_template_file = Mock()
        mock_template_file.exists.return_value = False

        mock_templates_dir = Mock()
        mock_templates_dir.__truediv__ = Mock(return_value=mock_template_file)
        mock_templates_dir.glob.return_value = [
            Mock(stem="notion.json"),
            Mock(stem="github.json"),
        ]
        mock_path.return_value.parent.__truediv__ = Mock(return_value=mock_templates_dir)

        with pytest.raises(ValueError) as exc_info:
            MCPClientFactory.from_provider("unsupported", {})

        assert "not supported" in str(exc_info.value).lower()

    def test_from_tool_config(self):
        """Test creating factory from tool config"""
        tool_config = {
            "mcpServers": {
                "customApi": {
                    "command": "npx",
                    "args": ["@example/mcp-server"],
                    "env": {"TOKEN": "{{ TOKEN }}"},
                }
            }
        }
        credentials = {"TOKEN": "test_token_123"}

        factory = MCPClientFactory.from_tool_config(tool_config, credentials)

        assert isinstance(factory, MCPClientFactory)
        assert factory.config_dict is not None
        # Verify credential substitution happened
        assert "test_token_123" in json.dumps(factory.config_dict)

    def test_from_tool_config_missing_mcp_servers(self):
        """Test creating factory from tool config without mcpServers raises ValueError"""
        tool_config = {"invalid": "config"}
        credentials = {}

        with pytest.raises(ValueError) as exc_info:
            MCPClientFactory.from_tool_config(tool_config, credentials)

        assert "mcpServers" in str(exc_info.value)

    def test_from_tool_config_credential_substitution(self):
        """Test credential substitution in tool config"""
        tool_config = {
            "mcpServers": {
                "testApi": {
                    "command": "npx",
                    "args": ["@test/server"],
                    "env": {
                        "API_KEY": "{{ API_KEY }}",
                        "API_SECRET": "{{ API_SECRET }}",
                    },
                }
            }
        }
        credentials = {"API_KEY": "key123", "API_SECRET": "secret456"}

        factory = MCPClientFactory.from_tool_config(tool_config, credentials)

        env = factory.config_dict["mcpServers"]["testApi"]["env"]
        assert env["API_KEY"] == "key123"
        assert env["API_SECRET"] == "secret456"
