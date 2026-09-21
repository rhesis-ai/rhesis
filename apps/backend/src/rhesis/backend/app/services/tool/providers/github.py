"""GitHub provider manifest.

``repository.owner`` and ``repository.repo`` are optional because the router has
never validated them: the frontend parses a repository URL and writes both, and
a tool saved without them still tests its connection as the authenticated user.
"""

from rhesis.backend.app.services.tool.providers._common import ApiTokenAuth, api_token_field
from rhesis.backend.app.services.tool.providers.spec import (
    FieldStore,
    ProviderField,
    ProviderManifest,
    ToolAction,
    Transport,
)
from rhesis.backend.app.services.tool.rest.github import GitHubRestClient

MANIFEST = ProviderManifest(
    key="github",
    display_name="GitHub",
    description="Pull files and docs from your repositories into your knowledge base",
    auth_methods=(
        ApiTokenAuth(
            label="Personal access token",
            help_url="https://github.com/settings/tokens",
        ),
    ),
    fields=(
        api_token_field("GITHUB_PERSONAL_ACCESS_TOKEN", label="Personal access token"),
        ProviderField(
            key="repository.owner",
            label="Repository owner",
            store=FieldStore.METADATA,
            required=False,
        ),
        ProviderField(
            key="repository.repo",
            label="Repository name",
            store=FieldStore.METADATA,
            required=False,
        ),
    ),
    actions={
        ToolAction.EXTRACT: Transport.REST,
        ToolAction.TEST_CONNECTION: Transport.REST,
    },
    rest_client=lambda c: GitHubRestClient(token=c.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")),
    mcp_template="github.json.j2",
)
