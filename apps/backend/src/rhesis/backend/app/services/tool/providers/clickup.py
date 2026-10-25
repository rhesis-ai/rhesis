"""ClickUp provider manifest."""

from rhesis.backend.app.services.tool.providers._common import ApiTokenAuth, api_token_field
from rhesis.backend.app.services.tool.providers.spec import (
    FieldStore,
    ProviderField,
    ProviderManifest,
    ToolAction,
    Transport,
)

MANIFEST = ProviderManifest(
    key="clickup",
    display_name="ClickUp",
    description="Import tasks and documents from ClickUp into your knowledge base",
    auth_methods=(
        ApiTokenAuth(
            label="Personal API token",
            help_url="https://developer.clickup.com/docs/authentication",
        ),
    ),
    fields=(
        api_token_field("CLICKUP_API_KEY", label="Personal API token"),
        ProviderField(
            key="CLICKUP_TEAM_ID",
            label="Workspace ID",
            store=FieldStore.CREDENTIALS,
            preserve_on_update=True,
            help_text="The workspace ID returned by the ClickUp API as team_id.",
        ),
    ),
    actions={
        ToolAction.EXTRACT: Transport.MCP,
        ToolAction.TEST_CONNECTION: Transport.MCP,
    },
    mcp_template="clickup.json.j2",
)
