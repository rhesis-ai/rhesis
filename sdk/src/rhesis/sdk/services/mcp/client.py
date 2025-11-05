"""MCP (Model Context Protocol) client for connecting to external data sources."""

import json
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters  # type: ignore[import-untyped]
from mcp.client.stdio import stdio_client  # type: ignore[import-untyped]


class MCPClient:
    """Client for interacting with MCP servers."""

    def __init__(
        self,
        server_name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize MCP client.

        Args:
            server_name: Name of the MCP server
            command: Command to run the MCP server (e.g., "npx")
            args: Arguments for the command (e.g., ["-y", "@notionhq/notion-mcp-server"])
            env: Optional environment variables for the server
        """
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env or {}
        self.session: Optional[ClientSession] = None
        self._read = None
        self._write = None
        self._stdio_context = None

    async def connect(self) -> None:
        """Connect to the MCP server."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )

        # stdio_client returns an async context manager
        stdio_context = stdio_client(server_params)
        self._read, self._write = await stdio_context.__aenter__()
        self._stdio_context = stdio_context  # Keep reference for cleanup

        self.session = ClientSession(self._read, self._write)
        await self.session.__aenter__()

        # Initialize the session
        await self.session.initialize()

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None

        if self._stdio_context:
            await self._stdio_context.__aexit__(None, None, None)
            self._stdio_context = None

    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources from the MCP server.

        Returns:
            List of resource dictionaries with uri, name, description, etc.
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        result = await self.session.list_resources()
        return [
            {
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mimeType if hasattr(resource, "mimeType") else None,
            }
            for resource in result.resources
        ]

    async def read_resource(self, uri: str) -> str:
        """
        Read content from a specific resource.

        Args:
            uri: The URI of the resource to read

        Returns:
            The text content of the resource
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        result = await self.session.read_resource(uri)

        # Extract text content from the response
        if result.contents:
            content_parts = []
            for content in result.contents:
                if hasattr(content, "text"):
                    content_parts.append(content.text)
                elif hasattr(content, "data"):
                    # Handle binary or other data types if needed
                    content_parts.append(str(content.data))
            return "\n".join(content_parts)

        return ""

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call a tool provided by the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Optional arguments for the tool

        Returns:
            The result of the tool call
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        result = await self.session.call_tool(tool_name, arguments or {})
        return result

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools from the MCP server.

        Returns:
            List of tool dictionaries with name, description, input schema
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        result = await self.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            }
            for tool in result.tools
        ]


class MCPClientManager:
    """Manager for multiple MCP clients."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize MCP client manager.

        Args:
            config_path: Optional path to MCP configuration file (mcp.json).
                        If not provided, will look for ~/.cursor/mcp.json
        """
        self.config_path = config_path
        self.clients: Dict[str, MCPClient] = {}

    def _load_config(self) -> Dict[str, Any]:
        """Load MCP configuration from file."""
        from pathlib import Path

        if self.config_path:
            config_file = Path(self.config_path)
        else:
            # Default to Cursor's MCP config location
            config_file = Path.home() / ".cursor" / "mcp.json"

        if not config_file.exists():
            raise FileNotFoundError(
                f"MCP configuration file not found at {config_file}. "
                "Please create it with your MCP server configurations."
            )

        with open(config_file, "r") as f:
            config = json.load(f)

        return config

    def create_client(self, server_name: str) -> MCPClient:
        """
        Create an MCP client from configuration.

        Args:
            server_name: Name of the MCP server from the config

        Returns:
            Configured MCPClient instance
        """
        config = self._load_config()

        if "mcpServers" not in config:
            raise ValueError("Invalid MCP configuration: 'mcpServers' key not found")

        if server_name not in config["mcpServers"]:
            available = ", ".join(config["mcpServers"].keys())
            raise ValueError(
                f"Server '{server_name}' not found in configuration. Available servers: {available}"
            )

        server_config = config["mcpServers"][server_name]

        # Parse environment variables if they're JSON strings
        env = {}
        if "env" in server_config:
            for key, value in server_config["env"].items():
                # Try to parse JSON strings
                if isinstance(value, str) and value.startswith("{"):
                    try:
                        # For headers like OPENAPI_MCP_HEADERS
                        env[key] = value
                    except json.JSONDecodeError:
                        env[key] = value
                else:
                    env[key] = value

        client = MCPClient(
            server_name=server_name,
            command=server_config["command"],
            args=server_config["args"],
            env=env,
        )

        self.clients[server_name] = client
        return client

    async def connect_all(self) -> None:
        """Connect to all configured MCP clients."""
        for client in self.clients.values():
            await client.connect()

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP clients."""
        for client in self.clients.values():
            await client.disconnect()
