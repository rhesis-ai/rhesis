"""Asana provider manifest."""

from rhesis.backend.app.services.tool.providers._common import ApiTokenAuth, api_token_field
from rhesis.backend.app.services.tool.providers.spec import (
    FieldStore,
    ProviderField,
    ProviderManifest,
    ToolAction,
    Transport,
)

MANIFEST = ProviderManifest(
    key="asana",
    display_name="Asana",
    description="Import tasks and projects from Asana into your knowledge base",
    auth_methods=(
        ApiTokenAuth(
            label="Personal access token",
            help_url="https://app.asana.com/0/my-apps",
        ),
    ),
    fields=(
        api_token_field("ASANA_ACCESS_TOKEN", label="Personal access token"),
        ProviderField(
            key="workspace_gid",
            label="Workspace",
            store=FieldStore.METADATA,
            required=False,
            help_text="Narrows imports to one workspace. Leave blank for all of them.",
        ),
    ),
    actions={
        ToolAction.EXTRACT: Transport.MCP,
        ToolAction.TEST_CONNECTION: Transport.MCP,
    },
    mcp_template="asana.json.j2",
)
