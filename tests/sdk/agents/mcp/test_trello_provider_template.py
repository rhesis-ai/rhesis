import json

from rhesis.sdk.agents.mcp.client import MCPClientFactory


def test_trello_provider_template_renders_valid_config():
    credentials = {
        "TRELLO_API_KEY": "trello_test_key_123",
        "TRELLO_TOKEN": "trello_test_token_456",
    }

    factory = MCPClientFactory.from_provider("trello", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["trello"]
    assert server["command"] == "npx"
    assert server["args"][1] == "@delano/mcp-trello"
    assert "@latest" not in " ".join(server["args"])
    assert server["env"]["TRELLO_API_KEY"] == "trello_test_key_123"
    assert server["env"]["TRELLO_TOKEN"] == "trello_test_token_456"

    rendered = json.dumps(factory.config_dict)
    assert "trello_test_key_123" in rendered
    assert "trello_test_token_456" in rendered
