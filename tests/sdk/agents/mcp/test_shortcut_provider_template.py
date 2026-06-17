import json

from rhesis.sdk.agents.mcp.client import MCPClientFactory


def test_shortcut_provider_template_renders_valid_config():
    credentials = {"SHORTCUT_API_TOKEN": "sc_test_token_123"}

    factory = MCPClientFactory.from_provider("shortcut", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["shortcut"]
    assert server["command"] == "npx"
    assert server["args"][1] == "@shortcut/mcp"
    assert "@latest" not in " ".join(server["args"])
    assert server["env"]["SHORTCUT_API_TOKEN"] == "sc_test_token_123"

    rendered = json.dumps(factory.config_dict)
    assert "sc_test_token_123" in rendered
