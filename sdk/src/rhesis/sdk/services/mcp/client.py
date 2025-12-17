"""MCP (Model Context Protocol) client for connecting to external data sources."""

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import jinja2
from mcp import ClientSession, StdioServerParameters  # type: ignore[import-untyped]
from mcp.client.sse import sse_client  # type: ignore[import-untyped]
from mcp.client.stdio import stdio_client  # type: ignore[import-untyped]
from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-untyped]


class MCPClient:
    """
    Client for connecting to and communicating with MCP servers.

    Supports multiple transport types (stdio, HTTP, SSE).
    """

    def __init__(
        self,
        server_name: str,
        transport_type: Literal["stdio", "http", "sse"],
        transport_params: Dict[str, Any],
    ):
        """
        Initialize MCP client with transport configuration.

        Args:
            server_name: Friendly name for the server (e.g., "notionApi")
            transport_type: Type of transport ("stdio", "http", or "sse")
            transport_params: Transport-specific parameters:
                - stdio: {"command": str, "args": List[str], "env": Dict[str, str]}
                - http: {"url": str, "headers": Dict[str, str]}
                - sse: {"url": str, "headers": Dict[str, str]}
        """
        self.server_name = server_name
        self.transport_type = transport_type
        self.transport_params = transport_params
        self.session: Optional[ClientSession] = None
        self._transport_context = None

    async def connect(self) -> None:
        """
        Connect to MCP server using the configured transport.

        Routes to transport-specific connection method based on transport type.
        Must be called before any other operations.
        """
        if self.transport_type == "stdio":
            await self._connect_stdio()
        elif self.transport_type == "http":
            await self._connect_http()
        elif self.transport_type == "sse":
            await self._connect_sse()

    async def _connect_stdio(self) -> None:
        """Connect via stdio transport."""
        server_params = StdioServerParameters(
            command=self.transport_params["command"],
            args=self.transport_params["args"],
            env=self.transport_params.get("env", {}),
        )

        # stdio_client returns an async context manager
        stdio_context = stdio_client(server_params)
        read, write = await stdio_context.__aenter__()
        self._transport_context = stdio_context

        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

    async def _connect_http(self) -> None:
        """Connect via HTTP/StreamableHTTP transport."""
        http_context = streamablehttp_client(
            url=self.transport_params["url"],
            headers=self.transport_params.get("headers", {}),
        )
        read, write, get_session_id = await http_context.__aenter__()
        self._transport_context = http_context

        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

    async def _connect_sse(self) -> None:
        """Connect via SSE transport."""
        sse_context = sse_client(
            url=self.transport_params["url"],
            headers=self.transport_params.get("headers", {}),
        )
        read, write = await sse_context.__aenter__()
        self._transport_context = sse_context

        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None

        if self._transport_context:
            await self._transport_context.__aexit__(None, None, None)
            self._transport_context = None

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


class MCPClientFactory:
    """
    Factory for creating MCP clients from configuration.

    Loads and parses MCP server configurations from files, dicts, or templates,
    detects transport types, and creates pre-configured MCPClient instances.
    """

    def __init__(self, config_path: Optional[str] = None, config_dict: Optional[Dict] = None):
        """
        Initialize client factory with config file path or config dict.

        Args:
            config_path: Path to mcp.json config file. Required if config_dict is not provided.
            config_dict: Direct configuration dictionary in MCP format:
                        {"mcpServers": {"serverName": {...}}}
                        Required if config_path is not provided.

        Raises:
            ValueError: If neither config_path nor config_dict is provided.
        """
        if not config_path and not config_dict:
            raise ValueError(
                "Either 'config_path' or 'config_dict' must be provided. "
                "Cannot default to any config location."
            )
        self.config_path = config_path
        self.config_dict = config_dict

    def _load_config(self) -> Dict[str, Any]:
        """
        Load MCP configuration from file or use provided config dict.

        Returns:
            Full MCP configuration with mcpServers structure
        """
        # If config_dict is provided, use it directly
        if self.config_dict:
            return self.config_dict

        # Load from file (config_path is guaranteed to be set by __init__)
        config_file = Path(self.config_path)

        if not config_file.exists():
            raise FileNotFoundError(
                f"MCP configuration file not found at {config_file}. "
                "Please create it with your MCP server configurations."
            )

        with open(config_file, "r") as f:
            config = json.load(f)

        return config

    def _detect_transport_type(
        self, server_config: Dict[str, Any]
    ) -> Literal["stdio", "http", "sse"]:
        """
        Auto-detect transport type from server configuration structure.

        Detection rules:
        - Has 'command' field → stdio
        - Has 'url' + 'headers' with Authorization → http
        - Has 'url' only → sse

        Args:
            server_config: Single server configuration dictionary

        Returns:
            Transport type: "stdio", "http", or "sse"

        Raises:
            ValueError: If transport type cannot be determined
        """
        if "command" in server_config:
            return "stdio"
        elif "url" in server_config:
            # Check if headers contain Authorization (typical for HTTP APIs)
            headers = server_config.get("headers", {})
            if headers and any(k.lower() == "authorization" for k in headers.keys()):
                return "http"
            else:
                return "sse"
        else:
            raise ValueError(
                "Cannot detect transport type from config. "
                "Config must have either 'command' (stdio) or 'url' (HTTP/SSE) field."
            )

    def create_client(self, server_name: str) -> MCPClient:
        """
        Create an MCP client from configuration.

        Loads config, detects transport type, and creates a pre-configured MCPClient instance.

        Args:
            server_name: Name of the MCP server from the config

        Returns:
            Configured MCPClient instance ready to connect

        Raises:
            ValueError: If server not found or config invalid
            FileNotFoundError: If config file doesn't exist
        """
        config = self._load_config()

        # Support both "mcpServers" and "servers" format
        servers = config.get("mcpServers") or config.get("servers")
        if not servers:
            raise ValueError("Invalid MCP configuration: no 'mcpServers' or 'servers' key found")

        if server_name not in servers:
            available = ", ".join(servers.keys())
            raise ValueError(f"Server '{server_name}' not found. Available: {available}")

        server_config = servers[server_name]

        # Detect transport type
        transport_type = self._detect_transport_type(server_config)

        # Create client with pre-configured transport
        client = MCPClient(
            server_name=server_name,
            transport_type=transport_type,
            transport_params=server_config,
        )

        return client

    @classmethod
    def from_tool_config(cls, tool_name: str, tool_config: Dict, credentials: Dict[str, str]):
        """
        Create MCPClientFactory from database tool configuration.

        The user provides the complete tool_metadata JSON in full MCP format with
        credential placeholders. This method substitutes the placeholders with
        the actual credential values.

        Args:
            tool_name: Name for the MCP server (e.g., "notionApi") - ignored if
                       tool_config contains mcpServers
            tool_config: Full MCP config with credential placeholders:
                        {"mcpServers": {"name": {...}}}
            credentials: Dictionary of credential key-value pairs

        Returns:
            MCPClientFactory instance configured with the tool

        Note:
            tool_config should be the full MCP structure matching standard format.
            This method performs credential substitution via Jinja2 templates.

        Example:
            tool_config = {
                "mcpServers": {
                    "notionApi": {
                        "command": "npx",
                        "args": ["-y", "@notionhq/notion-mcp-server"],
                        "env": {
                            "NOTION_TOKEN": "{{ NOTION_TOKEN }}"
                        }
                    }
                }
            }
            credentials = {"NOTION_TOKEN": "ntn_abc123..."}
            factory = MCPClientFactory.from_tool_config("notionApi", tool_config, credentials)
        """
        # Use Jinja to safely render the placeholders
        env = jinja2.Environment(autoescape=False)
        template = env.from_string(json.dumps(tool_config))
        rendered = template.render(**credentials)
        processed_config = json.loads(rendered)

        # Config should already have mcpServers structure
        # Validate it has the expected format
        if "mcpServers" not in processed_config:
            raise ValueError(
                "tool_config must contain 'mcpServers' key. "
                "Expected format: {'mcpServers': {'serverName': {...}}}"
            )

        return cls(config_dict=processed_config)

    @classmethod
    def from_provider(cls, provider: str, credentials: Dict[str, str]):
        """
        Create MCPClientFactory from a provider name.

        Automatically loads the right MCP config template for that provider,
        renders it with the provided credentials, and creates a factory.

        Args:
            provider: Provider name (e.g., "notion", "github", "atlassian")
            credentials: Dictionary of credential key-value pairs

        Returns:
            MCPClientFactory instance ready to use

        Example:
            credentials = {"NOTION_TOKEN": "ntn_abc123..."}
            factory = MCPClientFactory.from_provider("notion", credentials)
        """
        # Load and render Jinja template
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

        # Parse rendered JSON into dict (templates already include full mcpServers structure)
        config_dict = json.loads(rendered)

        # Validate structure
        if "mcpServers" not in config_dict:
            raise ValueError(
                f"Provider template for '{provider}' is invalid. "
                "Expected format: {'mcpServers': {'serverName': {...}}}"
            )

        return cls(config_dict=config_dict)
