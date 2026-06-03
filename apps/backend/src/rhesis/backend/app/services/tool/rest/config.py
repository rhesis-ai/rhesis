"""Resolve a DB tool to its REST client implementation via a provider registry."""

import json
import uuid
from typing import Callable, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp.exceptions import MCPConfigurationError

from .base import RestClient
from .confluence import ConfluenceRestClient
from .github import GitHubRestClient
from .jira import JiraRestClient
from .notion import NotionRestClient

# Maps provider type_value → factory(credentials) → RestClient
_PROVIDER_REGISTRY: Dict[str, Callable[[Dict[str, str]], RestClient]] = {
    "notion": lambda c: NotionRestClient(token=c.get("NOTION_TOKEN", "")),
    "github": lambda c: GitHubRestClient(token=c.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")),
    "jira": lambda c: JiraRestClient(
        base_url=c.get("JIRA_URL", ""),
        username=c.get("JIRA_USERNAME", ""),
        api_token=c.get("JIRA_API_TOKEN", ""),
    ),
    "confluence": lambda c: ConfluenceRestClient(
        base_url=c.get("CONFLUENCE_URL", ""),
        username=c.get("CONFLUENCE_USERNAME", ""),
        api_token=c.get("CONFLUENCE_API_TOKEN", ""),
    ),
}


def build_client(provider: str, credentials: Dict[str, str]) -> RestClient:
    """Instantiate the RestClient for *provider* using *credentials*.

    Raises:
        MCPConfigurationError: If no client is registered for *provider*.
    """
    factory = _PROVIDER_REGISTRY.get(provider)
    if factory is None:
        raise MCPConfigurationError(f"No REST client registered for provider '{provider}'")
    return factory(credentials)


def get_rest_source(
    db: Session, tool_id: str, organization_id: str, user_id: str = None
) -> RestClient:
    """Resolve a DB tool to its REST client.

    Raises:
        MCPConfigurationError: If tool not found, deleted, or provider unsupported.
    """
    try:
        tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
    except ItemDeletedException:
        raise MCPConfigurationError(
            f"Tool '{tool_id}' has been deleted. Please re-import the source."
        )

    if not tool:
        raise MCPConfigurationError(
            f"Tool '{tool_id}' not found. Please add it in /integrations/tools"
        )

    try:
        credentials = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise MCPConfigurationError(f"Invalid credentials for tool '{tool_id}': {e}")

    return build_client(tool.tool_provider_type.type_value, credentials)
