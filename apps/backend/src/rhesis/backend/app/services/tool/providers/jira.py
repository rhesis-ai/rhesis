"""Jira provider manifest.

``JIRA_URL`` is validated against the SSRF blocklist on create as well as on
update. The old router only checked it on update, so a tool created with a URL
resolving to link-local space was accepted and only rejected on the next edit.
"""

from rhesis.backend.app.services.tool.providers._common import (
    ApiTokenAuth,
    api_token_field,
    base_url_field,
)
from rhesis.backend.app.services.tool.providers.spec import (
    FieldMessages,
    FieldStore,
    ProviderField,
    ProviderManifest,
    ToolAction,
    Transport,
)
from rhesis.backend.app.services.tool.rest.jira import JiraRestClient

MANIFEST = ProviderManifest(
    key="jira",
    display_name="Jira",
    description="Create Jira issues directly from Rhesis tasks",
    auth_methods=(
        ApiTokenAuth(
            label="API token",
            help_url="https://id.atlassian.com/manage-profile/security",
        ),
    ),
    fields=(
        base_url_field("JIRA_URL", "Workspace URL", required=True),
        ProviderField(
            key="JIRA_USERNAME",
            label="Atlassian email",
            store=FieldStore.CREDENTIALS,
            required=False,
            preserve_on_update=True,
        ),
        api_token_field("JIRA_API_TOKEN"),
        ProviderField(
            key="space_key",
            label="Project key",
            store=FieldStore.METADATA,
            messages=FieldMessages(
                missing="Jira integrations require 'space_key'",
                invalid="Jira 'space_key' must be non-empty",
                container_missing="Jira integrations require 'space_key'",
            ),
        ),
    ),
    actions={
        ToolAction.TEST_CONNECTION: Transport.REST,
        ToolAction.CREATE_TICKET: Transport.REST,
    },
    rest_client=lambda c: JiraRestClient(
        base_url=c.get("JIRA_URL", ""),
        username=c.get("JIRA_USERNAME", ""),
        api_token=c.get("JIRA_API_TOKEN", ""),
    ),
    mcp_template="jira.json.j2",
)
