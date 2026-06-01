"""Resolve a DB tool to its REST source implementation."""

import json
import uuid
from typing import Union

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp.exceptions import MCPConfigurationError

from .github import GitHubSource
from .notion import NotionSource


def get_rest_source(
    db: Session, tool_id: str, organization_id: str, user_id: str = None
) -> Union[NotionSource, GitHubSource]:
    """Resolve a REST-capable tool to its source implementation.

    Valid for tools with tool_type 'api' or 'hybrid'.

    Raises:
        MCPConfigurationError: If tool not found, deleted, or does not support REST.
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

    if tool.tool_type.type_value not in ("api", "hybrid"):
        raise MCPConfigurationError(f"Tool '{tool.name}' does not support REST")

    try:
        credentials = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise MCPConfigurationError(f"Invalid credentials for tool '{tool_id}': {e}")

    provider = tool.tool_provider_type.type_value

    if provider == "notion":
        return NotionSource(token=credentials.get("NOTION_TOKEN", ""))

    if provider == "github":
        return GitHubSource(token=credentials.get("GITHUB_PERSONAL_ACCESS_TOKEN", ""))

    raise MCPConfigurationError(f"No REST implementation found for provider '{provider}'")
