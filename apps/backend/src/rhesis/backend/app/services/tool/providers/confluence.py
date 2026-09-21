"""Confluence provider manifest."""

from rhesis.backend.app.services.tool.providers._common import (
    ApiTokenAuth,
    api_token_field,
    base_url_field,
)
from rhesis.backend.app.services.tool.providers.spec import (
    FieldStore,
    ProviderField,
    ProviderManifest,
    ToolAction,
    Transport,
)
from rhesis.backend.app.services.tool.rest.confluence import ConfluenceRestClient

MANIFEST = ProviderManifest(
    key="confluence",
    display_name="Confluence",
    description="Import spaces and pages from Confluence into your knowledge base",
    auth_methods=(
        ApiTokenAuth(
            label="API token",
            help_url="https://id.atlassian.com/manage-profile/security",
        ),
    ),
    fields=(
        base_url_field("CONFLUENCE_URL", "Workspace URL", required=True),
        ProviderField(
            key="CONFLUENCE_USERNAME",
            label="Atlassian email",
            store=FieldStore.CREDENTIALS,
            preserve_on_update=True,
            help_text="The account the API token belongs to.",
        ),
        api_token_field("CONFLUENCE_API_TOKEN"),
        ProviderField(
            key="space_key",
            label="Space",
            store=FieldStore.METADATA,
            required=False,
        ),
    ),
    actions={ToolAction.TEST_CONNECTION: Transport.REST},
    rest_client=lambda c: ConfluenceRestClient(
        base_url=c.get("CONFLUENCE_URL", ""),
        username=c.get("CONFLUENCE_USERNAME", ""),
        api_token=c.get("CONFLUENCE_API_TOKEN", ""),
    ),
    mcp_template="confluence.json.j2",
)
