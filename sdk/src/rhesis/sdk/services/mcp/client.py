"""MCP (Model Context Protocol) client for connecting to external data sources."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Jinja is used for template rendering
import jinja2
from mcp import ClientSession, StdioServerParameters  # type: ignore[import-untyped]
from mcp.client.stdio import stdio_client  # type: ignore[import-untyped]


class MCPClient:
    """
    Client for connecting to and communicating with MCP servers.

    Manages stdio-based communication with external MCP servers (Notion, GitHub, etc.)
    and provides methods to list/call tools and read resources.
    """

    def __init__(
        self,
        server_name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize MCP client for a specific server.

        Args:
            server_name: Friendly name for the server (e.g., "notionApi")
            command: Command to launch the server (e.g., "bunx", "python")
            args: Command arguments (e.g., ["--bun", "@notionhq/notion-mcp-server"])
            env: Environment variables to pass to the server process
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
        """
        Start the MCP server subprocess and establish connection.

        Must be called before any other operations.
        """
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
        List all tools exposed by this MCP server.

        Returns:
            List of dicts with 'name', 'description', and 'inputSchema' fields
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
    """
    Factory for creating MCP clients from configuration files.

    Loads server configurations from mcp.json and creates MCPClient instances.
    """

    def __init__(self, config_path: Optional[str] = None, config_dict: Optional[Dict] = None):
        """
        Initialize client manager with config file path or config dict.

        Args:
            config_path: Path to mcp.json config file.
                        Defaults to ~/.cursor/mcp.json if not provided
            config_dict: Direct configuration dictionary (for database tools)
        """
        self.config_path = config_path
        self.config_dict = config_dict
        self.clients: Dict[str, MCPClient] = {}

    def _load_config(self) -> Dict[str, Any]:
        """Load MCP configuration from file or use provided config dict."""
        # If config_dict is provided, use it directly
        if self.config_dict:
            return self.config_dict

        # Otherwise load from file
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

        client = MCPClient(
            server_name=server_name,
            command=server_config["command"],
            args=server_config["args"],
            env=server_config.get("env"),
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

    @classmethod
    def from_tool_config(cls, tool_name: str, tool_config: Dict, credentials: Dict[str, str]):
        """
        Create MCPClientManager from database tool configuration.

        The user provides the complete tool_metadata JSON with credential placeholders.
        This method substitutes the placeholders with the actual credential values.

        Args:
            tool_name: Name for the MCP server (e.g., "notionApi")
            tool_config: Tool metadata dict with credential placeholders like {{NOTION_TOKEN}}
            credentials: Dictionary of credential key-value pairs

        Returns:
            MCPClientManager instance configured with the tool

        Note:
            Placeholders must use simple format like {{ TOKEN }} (not {{ TOKEN | tojson }})
            because the tool_config must be valid JSON before Jinja2 rendering.

        Example:
            tool_config = {
                "command": "bunx",
                "args": ["--bun", "@notionhq/notion-mcp-server"],
                "env": {
                    "NOTION_TOKEN": "{{ NOTION_TOKEN }}"
                }
            }
            credentials = {"NOTION_TOKEN": "ntn_abc123..."}
            manager = MCPClientManager.from_tool_config("notionApi", tool_config, credentials)
        """
        # Use Jinja to safely render the placeholders without breaking JSON
        env = jinja2.Environment(autoescape=False)
        template = env.from_string(json.dumps(tool_config))
        rendered = template.render(**credentials)
        processed_config = json.loads(rendered)

        # Wrap in mcpServers format expected by create_client
        config_dict = {"mcpServers": {tool_name: processed_config}}

        return cls(config_dict=config_dict)

    @classmethod
    def from_provider(cls, provider: str, credentials: Dict[str, str]):
        """
        Create MCPClientManager from a provider name.

        Automatically loads the right MCP config for that provider,
        renders it with the provided credentials, and creates a manager.

        Args:
            provider: Provider name (e.g., "notion", "github", "gdrive")
            credentials: Dictionary of credential key-value pairs

        Returns:
            MCPClientManager instance ready to use

        Example:
            credentials = {"NOTION_TOKEN": "ntn_abc123..."}
            manager = MCPClientManager.from_provider("notion", credentials)
        """
        # -----------------------------
        # Load and render Jinja template
        # -----------------------------
        templates_dir = Path(__file__).parent / "provider_templates"
        template_file = templates_dir / f"{provider}.json.j2"

        if not template_file.exists():
            # Provide a helpful error listing available providers
            available = [p.stem.split(".")[0] for p in templates_dir.glob("*.json.j2")]
            raise ValueError(f"MCP provider '{provider}' not supported. Available: {available}")

        env = jinja2.Environment(autoescape=False)
        template = env.from_string(template_file.read_text())

        # Render with proper JSON-escaping via the built-in `tojson` filter
        rendered = template.render(**credentials)

        # Parse rendered JSON into dict
        config = json.loads(rendered)

        # Build manager configuration
        tool_name = f"{provider}Api"
        config_dict = {"mcpServers": {tool_name: config}}

        return cls(config_dict=config_dict)
