"""MCP client resolution from tools and request parameters."""

import json
import uuid
from typing import Dict

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp import MCPClientFactory


def _get_mcp_tool_config(db: Session, tool_id: str, organization_id: str, user_id: str = None):
    """
    Get MCP client and provider configuration from database by tool ID.

    Args:
        db: Database session
        tool_id: Tool instance ID
        organization_id: Organization ID (for authorization check)
        user_id: User ID (for authorization check)

    Returns:
        Tuple of (MCPClient, provider_name, repository_context) ready to use.
        repository_context is None or a dict with 'owner', 'repo', 'full_name'
        for GitHub repository-scoped connections.

    Raises:
        ToolConfigurationError: If tool not found, deleted, not an MCP integration,
            or invalid credentials
    """
    try:
        tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
    except ItemDeletedException:
        raise ToolConfigurationError(
            f"Tool '{tool_id}' has been deleted. Please re-import the source."
        )

    if not tool:
        raise ToolConfigurationError(
            f"Tool '{tool_id}' not found. Please add it in /integrations/tools"
        )

    # Get provider name for the client
    provider = tool.tool_provider_type.type_value

    # Parse credentials JSON
    try:
        credentials_dict = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise ToolConfigurationError(f"Invalid credentials format for tool '{tool_id}': {e}")

    repository_context = None

    factory = MCPClientFactory.from_provider(
        provider=provider,
        credentials=credentials_dict,
    )
    client = factory.create_client(provider)
    return client, provider, repository_context


def _get_mcp_client_from_params(
    provider_type_id: uuid.UUID,
    credentials: Dict[str, str],
    db: Session,
    organization_id: str,
    user_id: str = None,
):
    """
    Get MCP client from parameters without requiring a tool in the database.

    Args:
        provider_type_id: UUID of the provider type (TypeLookup)
        credentials: Dictionary of credential key-value pairs
        db: Database session
        organization_id: Organization ID (for authorization check)
        user_id: User ID (for authorization check)

    Returns:
        MCPClient ready to use

    Raises:
        ValueError: If provider not found, invalid configuration, or missing required fields
    """
    # Fetch provider type from database
    provider_type = crud.get_type_lookup(db, provider_type_id, organization_id, user_id)

    if not provider_type:
        raise ValueError(
            f"Provider type '{provider_type_id}' not found. Please verify the provider_type_id."
        )

    # Get provider name for the client
    provider = provider_type.type_value

    factory = MCPClientFactory.from_provider(
        provider=provider,
        credentials=credentials,
    )
    client = factory.create_client(provider)
    return client
