import json

from rhesis.sdk.agents.mcp.client import MCPClientFactory


def test_linear_provider_template_renders_valid_config():
    credentials = {"LINEAR_API_KEY": "linear_test_key_123"}

    factory = MCPClientFactory.from_provider("linear", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["linear"]
    assert server["command"] == "npx"
    assert server["args"][1] == "@linear/mcp-server"
    assert "@latest" not in " ".join(server["args"])
    assert server["env"]["LINEAR_API_KEY"] == "linear_test_key_123"

    rendered = json.dumps(factory.config_dict)
    assert "linear_test_key_123" in rendered
