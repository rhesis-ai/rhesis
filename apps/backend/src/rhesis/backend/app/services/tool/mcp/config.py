"""MCP client resolution from tools and request parameters."""

import json
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app.crud import tool as tool_crud
from rhesis.backend.app.crud import type_lookup as type_lookup_crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.providers import (
    FieldStore,
    ProviderFieldError,
    get_manifest,
    read_field,
    validate_field,
)
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp import MCPClientFactory


def _scope_context_from_metadata(
    provider: str, tool_metadata: Optional[Dict[str, Any]]
) -> Optional[Dict[str, str]]:
    """Narrow an MCP agent to the repo, workspace or project the tool names.

    Every metadata field a provider declares is scope: GitLab's namespace,
    Asana's workspace, Azure DevOps' project. Reached only on the MCP path, so
    REST-only providers never get here.
    """
    if not tool_metadata:
        return None

    manifest = get_manifest(provider)
    if manifest is None:
        return None

    context: Dict[str, str] = {}
    for field in manifest.fields_in(FieldStore.METADATA):
        # Keyed on the outermost segment, not the leaf: metadata that names
        # ``project`` but carries no usable ``project.namespace`` is malformed,
        # not absent. Skipping it would run the agent against everything the
        # token can reach instead of the one project the tool names.
        if field.path[0] not in tool_metadata:
            continue
        try:
            validate_field(manifest, field, tool_metadata)
        except ProviderFieldError as exc:
            raise ToolConfigurationError(str(exc)) from exc

        _, value = read_field(tool_metadata, field)
        if isinstance(value, str) and value.strip():
            context[field.leaf] = value.strip()

    return context or None


def _get_mcp_tool_config(
    db: Session,
    tool_id: str,
    organization_id: str,
    user_id: str | None = None,
    tool_metadata_override: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, str, Optional[Dict[str, str]]]:
    """Return MCP client, provider name, and optional provider scope context."""
    try:
        tool = tool_crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
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
    scope_context = _scope_context_from_metadata(provider, metadata)

    factory = MCPClientFactory.from_provider(
        provider=provider,
        credentials=credentials_dict,
    )
    client = factory.create_client(provider)
    return client, provider, scope_context


def _get_mcp_client_from_params(
    provider_type_id: uuid.UUID,
    credentials: Dict[str, str],
    db: Session,
    organization_id: str,
    user_id: str | None = None,
    tool_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, str, Optional[Dict[str, str]]]:
    """Build an MCP client from unsaved credentials (connection test before save)."""
    provider_type = type_lookup_crud.get_type_lookup(db, provider_type_id, organization_id, user_id)

    if not provider_type:
        raise ValueError(
            f"Provider type '{provider_type_id}' not found. Please verify the provider_type_id."
        )

    provider = provider_type.type_value
    scope_context = _scope_context_from_metadata(provider, tool_metadata)

    factory = MCPClientFactory.from_provider(
        provider=provider,
        credentials=credentials,
    )
    client = factory.create_client(provider)
    return client, provider, scope_context
