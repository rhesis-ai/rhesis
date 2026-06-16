"""MCP client resolution from tools and request parameters."""

import json
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp import MCPClientFactory


def _project_context_from_metadata(
    provider: str, tool_metadata: Optional[Dict[str, Any]]
) -> Optional[Dict[str, str]]:
    if provider != "gitlab" or not tool_metadata or "project" not in tool_metadata:
        return None
    project_data = tool_metadata["project"]
    namespace = project_data.get("namespace") if isinstance(project_data, dict) else None
    if not isinstance(namespace, str) or not namespace.strip() or "/" not in namespace.strip():
        raise ToolConfigurationError(
            "GitLab tool has invalid project metadata; namespace must be a group/project path"
        )
    return {"namespace": namespace.strip()}


def _get_mcp_tool_config(
    db: Session,
    tool_id: str,
    organization_id: str,
    user_id: str = None,
    tool_metadata_override: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, str, Optional[Dict[str, str]]]:
    """Return MCP client, provider name, and optional GitLab project context."""
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

    provider = tool.tool_provider_type.type_value

    try:
        credentials_dict = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise ToolConfigurationError(f"Invalid credentials format for tool '{tool_id}': {e}")

    metadata = tool_metadata_override if tool_metadata_override is not None else tool.tool_metadata
    project_context = _project_context_from_metadata(provider, metadata)

    factory = MCPClientFactory.from_provider(
        provider=provider,
        credentials=credentials_dict,
    )
    client = factory.create_client(provider)
    return client, provider, project_context


def _get_mcp_client_from_params(
    provider_type_id: uuid.UUID,
    credentials: Dict[str, str],
    db: Session,
    organization_id: str,
    user_id: str = None,
    tool_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, str, Optional[Dict[str, str]]]:
    """Build an MCP client from unsaved credentials (connection test before save)."""
    provider_type = crud.get_type_lookup(db, provider_type_id, organization_id, user_id)

    if not provider_type:
        raise ValueError(
            f"Provider type '{provider_type_id}' not found. Please verify the provider_type_id."
        )

    provider = provider_type.type_value
    project_context = _project_context_from_metadata(provider, tool_metadata)

    factory = MCPClientFactory.from_provider(
        provider=provider,
        credentials=credentials,
    )
    client = factory.create_client(provider)
    return client, provider, project_context
