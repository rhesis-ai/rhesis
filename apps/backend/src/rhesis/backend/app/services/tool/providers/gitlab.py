"""GitLab provider manifest."""

from rhesis.backend.app.services.tool.providers._common import (
    ApiTokenAuth,
    api_token_field,
    must_be_namespace,
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
    key="gitlab",
    display_name="GitLab",
    description="Import issues, merge requests, and wiki pages from GitLab projects",
    auth_methods=(
        ApiTokenAuth(
            label="Personal access token",
            help_url="https://docs.gitlab.com/user/profile/personal_access_tokens/",
        ),
    ),
    fields=(
        api_token_field("GITLAB_PERSONAL_ACCESS_TOKEN", label="Personal access token"),
        ProviderField(
            key="GITLAB_API_URL",
            label="GitLab API URL",
            store=FieldStore.CREDENTIALS,
            required=False,
            preserve_on_update=True,
            help_text="Self-managed instances only. Leave blank for gitlab.com.",
        ),
        ProviderField(
            key="project.namespace",
            label="Project",
            store=FieldStore.METADATA,
            placeholder="my-group/my-project",
            validate=must_be_namespace,
            messages=FieldMessages(
                missing="GitLab project must include 'namespace'",
                invalid="GitLab 'namespace' must be a non-empty group/project path",
                container_missing="GitLab integrations require project metadata",
            ),
        ),
    ),
    actions={
        ToolAction.EXTRACT: Transport.MCP,
        ToolAction.TEST_CONNECTION: Transport.MCP,
    },
    mcp_template="gitlab.json.j2",
)
