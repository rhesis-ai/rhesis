"""Azure DevOps provider manifest.

``AZURE_DEVOPS_ORG`` normalizes before it validates: users paste a full
``dev.azure.com/org`` or ``org.visualstudio.com`` URL as often as a bare name,
and the normalizer extracts the name from either while rejecting anything that
is still a URL afterwards.
"""

from rhesis.backend.app.services.tool.providers._common import (
    ApiTokenAuth,
    api_token_field,
    azure_devops_org,
)
from rhesis.backend.app.services.tool.providers.spec import (
    FieldMessages,
    FieldStore,
    ProviderField,
    ProviderManifest,
    ToolAction,
    Transport,
)

MANIFEST = ProviderManifest(
    key="azure_devops",
    display_name="Azure DevOps",
    description="Import work items, epics, and user stories from Azure DevOps boards",
    auth_methods=(
        ApiTokenAuth(
            label="Personal access token",
            help_url="https://learn.microsoft.com/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate",
        ),
    ),
    fields=(
        ProviderField(
            key="AZURE_DEVOPS_ORG",
            label="Organization",
            store=FieldStore.CREDENTIALS,
            preserve_on_update=True,
            placeholder="my-org",
            normalize=azure_devops_org,
        ),
        ProviderField(
            key="AZURE_DEVOPS_EMAIL",
            label="Account email",
            store=FieldStore.CREDENTIALS,
            preserve_on_update=True,
        ),
        api_token_field("AZURE_DEVOPS_PAT", label="Personal access token"),
        ProviderField(
            key="project",
            label="Project",
            store=FieldStore.METADATA,
            messages=FieldMessages(
                missing="Azure DevOps integrations require project metadata",
                invalid="Azure DevOps 'project' must be a non-empty string",
                container_missing="Azure DevOps integrations require project metadata",
            ),
        ),
    ),
    actions={
        ToolAction.EXTRACT: Transport.MCP,
        ToolAction.TEST_CONNECTION: Transport.MCP,
    },
    mcp_template="azure_devops.json.j2",
)
