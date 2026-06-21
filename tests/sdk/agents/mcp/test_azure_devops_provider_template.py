import base64
import json

from rhesis.sdk.agents.mcp.client import MCPClientFactory


def test_azure_devops_provider_template_renders_valid_config():
    credentials = {
        "AZURE_DEVOPS_ORG": "contoso",
        "AZURE_DEVOPS_EMAIL": "user@example.com",
        "AZURE_DEVOPS_PAT": "azure_test_pat_123",
    }

    factory = MCPClientFactory.from_provider("azure_devops", credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"]["azure_devops"]
    assert server["command"] == "npx"
    assert server["args"] == [
        "-y",
        "@azure-devops/mcp",
        "contoso",
        "--authentication",
        "pat",
    ]
    assert "@latest" not in " ".join(server["args"])
    expected_token = base64.b64encode(
        b"user@example.com:azure_test_pat_123"
    ).decode("ascii")
    assert server["env"]["PERSONAL_ACCESS_TOKEN"] == expected_token

    rendered = json.dumps(factory.config_dict)
    assert "azure_test_pat_123" not in rendered
    assert expected_token in rendered
