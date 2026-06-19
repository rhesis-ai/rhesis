import json

from rhesis.sdk.agents.mcp.client import MCPClientFactory


def test_azure_devops_provider_template_renders_valid_config():
    credentials = {
        "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/contoso",
        "AZURE_DEVOPS_PAT": "azure_test_pat_123",
    }

    factory = MCPClientFactory.from_provider("azure_devops", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["azure_devops"]
    assert server["command"] == "npx"
    assert server["args"][1] == "@tiberriver256/mcp-server-azure-devops"
    assert "@latest" not in " ".join(server["args"])
    assert server["env"]["AZURE_DEVOPS_ORG_URL"] == "https://dev.azure.com/contoso"
    assert server["env"]["AZURE_DEVOPS_AUTH_METHOD"] == "pat"
    assert server["env"]["AZURE_DEVOPS_PAT"] == "azure_test_pat_123"

    rendered = json.dumps(factory.config_dict)
    assert "azure_test_pat_123" in rendered
