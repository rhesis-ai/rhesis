import pytest

from rhesis.sdk.agents.mcp.client import MCPClientFactory


@pytest.mark.parametrize(
    "api_key",
    [
        "clickup_test_token_123",
        'token"with\\slashes\nand-newlines',
    ],
    ids=["plain-token", "json-sensitive-token"],
)
def test_clickup_provider_template_renders_valid_config(api_key):
    credentials = {
        "CLICKUP_API_KEY": api_key,
        "CLICKUP_TEAM_ID": "123456789",
    }

    factory = MCPClientFactory.from_provider("clickup", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["clickup"]
    assert server["transport"] == "stdio"
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "@hauptsache.net/clickup-mcp@1.9.0"]
    assert server["env"] == {
        "CLICKUP_API_KEY": api_key,
        "CLICKUP_TEAM_ID": "123456789",
        "CLICKUP_MCP_MODE": "read",
    }
