"""Jira and Confluence both launch the same server through ``uvx``.

``uvx`` reads ``name@version`` as ``name==version`` -- a version that does not
exist fails to resolve rather than falling back to the latest -- so the pin in
these templates is what decides which server actually runs.
"""

import json

import pytest

from rhesis.sdk.agents.mcp.client import MCPClientFactory

MCP_ATLASSIAN_SPEC = "mcp-atlassian@0.23.1"

PROVIDERS = [
    pytest.param(
        "jira",
        {
            "JIRA_URL": "https://example.atlassian.net",
            "JIRA_USERNAME": "user@example.com",
            "JIRA_API_TOKEN": "jira_test_token_123",
        },
        id="jira",
    ),
    pytest.param(
        "confluence",
        {
            "CONFLUENCE_URL": "https://example.atlassian.net/wiki",
            "CONFLUENCE_USERNAME": "user@example.com",
            "CONFLUENCE_API_TOKEN": "confluence_test_token_123",
        },
        id="confluence",
    ),
]


@pytest.mark.parametrize("provider,credentials", PROVIDERS)
def test_provider_template_renders_valid_config(provider: str, credentials: dict):
    factory = MCPClientFactory.from_provider(provider, credentials)

    assert factory.config_dict is not None
    server = factory.config_dict["mcpServers"][provider]
    assert server["command"] == "uvx"
    assert server["args"] == [MCP_ATLASSIAN_SPEC]
    assert "@latest" not in " ".join(server["args"])

    for name, value in credentials.items():
        assert server["env"][name] == value

    rendered = json.dumps(factory.config_dict)
    for value in credentials.values():
        assert value in rendered
