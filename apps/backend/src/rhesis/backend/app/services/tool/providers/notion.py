"""Notion provider manifest."""

from rhesis.backend.app.services.tool.providers._common import ApiTokenAuth, api_token_field
from rhesis.backend.app.services.tool.providers.spec import (
    ProviderManifest,
    ToolAction,
    Transport,
)
from rhesis.backend.app.services.tool.rest.notion import NotionRestClient

MANIFEST = ProviderManifest(
    key="notion",
    display_name="Notion",
    description="Pull pages and databases into your knowledge base as test context",
    auth_methods=(
        ApiTokenAuth(
            label="Internal integration token",
            help_url="https://www.notion.so/profile/integrations/internal/",
        ),
    ),
    fields=(api_token_field("NOTION_TOKEN", label="Integration token"),),
    actions={
        ToolAction.EXTRACT: Transport.REST,
        ToolAction.TEST_CONNECTION: Transport.REST,
    },
    rest_client=lambda c: NotionRestClient(token=c.get("NOTION_TOKEN", "")),
    mcp_template="notion.json.j2",
)
