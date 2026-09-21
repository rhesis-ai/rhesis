"""Shortcut provider manifest.

Shortcut has no OAuth of any kind: its API is token-only, so ``api_token`` is
not a fallback here, it is the whole story.
"""

from rhesis.backend.app.services.tool.providers._common import ApiTokenAuth, api_token_field
from rhesis.backend.app.services.tool.providers.spec import (
    ProviderManifest,
    ToolAction,
    Transport,
)

MANIFEST = ProviderManifest(
    key="shortcut",
    display_name="Shortcut",
    description="Import stories and epics from Shortcut into your knowledge base",
    auth_methods=(
        ApiTokenAuth(
            label="API token",
            help_url="https://app.shortcut.com/settings/account/api-tokens",
        ),
    ),
    fields=(api_token_field("SHORTCUT_API_TOKEN"),),
    actions={
        ToolAction.EXTRACT: Transport.MCP,
        ToolAction.TEST_CONNECTION: Transport.MCP,
    },
    mcp_template="shortcut.json.j2",
)
