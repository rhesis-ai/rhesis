"""Trello provider manifest.

Both credentials are ``preserve_on_update``: the key and the token are issued
separately in Trello's Power-Up admin, and an edit that replaces one must not
blank the other.
"""

from rhesis.backend.app.services.tool.providers._common import ApiTokenAuth, api_token_field
from rhesis.backend.app.services.tool.providers.spec import (
    FieldStore,
    ProviderField,
    ProviderManifest,
    ToolAction,
    Transport,
)

MANIFEST = ProviderManifest(
    key="trello",
    display_name="Trello",
    description="Import boards, lists, and cards from Trello into your knowledge base",
    auth_methods=(
        ApiTokenAuth(
            label="API key and token",
            help_url="https://trello.com/power-ups/admin",
        ),
    ),
    fields=(
        ProviderField(
            key="TRELLO_API_KEY",
            label="API key",
            store=FieldStore.CREDENTIALS,
            preserve_on_update=True,
        ),
        api_token_field("TRELLO_TOKEN", label="Token", preserve_on_update=True),
    ),
    actions={
        ToolAction.EXTRACT: Transport.MCP,
        ToolAction.TEST_CONNECTION: Transport.MCP,
    },
    mcp_template="trello.json.j2",
)
