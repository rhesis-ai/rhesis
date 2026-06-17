import json

from rhesis.sdk.agents.mcp.client import MCPClientFactory


def test_asana_provider_template_renders_valid_config():
    credentials = {"ASANA_ACCESS_TOKEN": "asana_test_token_123"}

    factory = MCPClientFactory.from_provider("asana", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["asana"]
    assert server["command"] == "npx"
    assert "@roychri/mcp-server-asana" in server["args"]
    assert "@latest" not in " ".join(server["args"])
    assert server["env"]["ASANA_ACCESS_TOKEN"] == "asana_test_token_123"

    rendered = json.dumps(factory.config_dict)
    assert "asana_test_token_123" in rendered
