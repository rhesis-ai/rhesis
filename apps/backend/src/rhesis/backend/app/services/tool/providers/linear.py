"""Linear provider manifest."""

from rhesis.backend.app.services.tool.providers._common import ApiTokenAuth, api_token_field
from rhesis.backend.app.services.tool.providers.spec import (
    ProviderManifest,
    ToolAction,
    Transport,
)

MANIFEST = ProviderManifest(
    key="linear",
    display_name="Linear",
    description="Import issues and project context from Linear into your knowledge base",
    auth_methods=(
        ApiTokenAuth(
            label="API key",
            help_url="https://linear.app/settings/account/security",
        ),
    ),
    fields=(api_token_field("LINEAR_API_TOKEN", label="API key"),),
    actions={
        ToolAction.EXTRACT: Transport.MCP,
        ToolAction.TEST_CONNECTION: Transport.MCP,
    },
    mcp_template="linear.json.j2",
)
