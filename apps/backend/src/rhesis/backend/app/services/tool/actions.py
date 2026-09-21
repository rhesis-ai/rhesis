"""Per-(provider, action) transport routing for tool operations.

A tool operation (extract content, test connection, create a ticket) can be
served by a deterministic REST call or an LLM-driven MCP agent. The choice is
made **per action, per provider** -- not per provider -- so the same provider
can serve one action over REST and another over MCP.

The table itself lives on each provider's manifest (``manifest.actions``). A
missing entry means the provider does not support that action. When a provider
eventually needs both transports for the *same* action, that cell carries both
plus a selection policy here -- callers are unaffected, they only ask for
``route(provider, action)``.
"""

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud import tool as tool_crud
from rhesis.backend.app.crud import type_lookup as type_lookup_crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.providers import get_manifest
from rhesis.backend.app.services.tool.providers.spec import ToolAction, Transport
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException


def route(provider: str, action: ToolAction) -> Transport:
    """Return the transport for *provider*/*action*.

    Raises:
        ToolConfigurationError: If the provider does not support the action.
    """
    manifest = get_manifest(provider)
    transport = manifest.actions.get(action) if manifest else None
    if transport is None:
        raise ToolConfigurationError(
            f"Provider '{provider}' does not support action '{action.value}'."
        )
    return transport


def resolve_provider(
    db: Session,
    organization_id: str,
    *,
    tool_id: Optional[str] = None,
    provider_type_id: Optional[uuid.UUID] = None,
    user_id: Optional[str] = None,
) -> str:
    """Resolve the provider ``type_value`` from a saved tool or a provider type.

    Raises:
        ToolConfigurationError: If the tool/provider type cannot be found.
    """
    if tool_id is not None:
        try:
            tool = tool_crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
        except ItemDeletedException:
            raise ToolConfigurationError(
                f"Tool '{tool_id}' has been deleted. Please re-import the source."
            )
        if not tool:
            raise ToolConfigurationError(f"Tool '{tool_id}' not found.")
        return tool.tool_provider_type.type_value

    provider_type = type_lookup_crud.get_type_lookup(db, provider_type_id, organization_id, user_id)
    if not provider_type:
        raise ToolConfigurationError(f"Provider type '{provider_type_id}' not found.")
    return provider_type.type_value
