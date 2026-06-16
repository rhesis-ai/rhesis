import json

from rhesis.sdk.agents.mcp.client import MCPClientFactory


def test_gitlab_provider_template_renders_valid_config():
    credentials = {"GITLAB_PERSONAL_ACCESS_TOKEN": "glpat_test_token_123"}

    factory = MCPClientFactory.from_provider("gitlab", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["gitlab"]
    assert server["command"] == "npx"
    assert "@zereight/mcp-gitlab" in server["args"]
    assert "@latest" not in " ".join(server["args"])
    assert server["env"]["GITLAB_PERSONAL_ACCESS_TOKEN"] == "glpat_test_token_123"
    assert server["env"]["GITLAB_API_URL"] == "https://gitlab.com/api/v4"
    assert server["env"]["GITLAB_READ_ONLY_MODE"] == "true"
    assert server["env"]["USE_GITLAB_WIKI"] == "true"

    rendered = json.dumps(factory.config_dict)
    assert "glpat_test_token_123" in rendered


def test_gitlab_provider_template_honors_custom_api_url():
    credentials = {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "glpat_test_token_123",
        "GITLAB_API_URL": "https://gitlab.example.com/api/v4",
    }

    factory = MCPClientFactory.from_provider("gitlab", credentials)
    server = factory.config_dict["mcpServers"]["gitlab"]
    assert server["env"]["GITLAB_API_URL"] == "https://gitlab.example.com/api/v4"
