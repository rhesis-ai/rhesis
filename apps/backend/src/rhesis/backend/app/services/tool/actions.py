"""Per-(provider, action) transport routing for tool operations.

A tool operation (extract content, test connection, create a ticket) can be served by
a deterministic REST call or an LLM-driven MCP agent. The choice is made **per action,
per provider** — not per provider — so the same provider can serve one action over REST
and another over MCP.

``_ROUTES`` is the declarative table: which transport handles each cell. A missing cell
means the provider does not support that action. When a provider eventually needs both
transports for the *same* action, change that cell's value to carry both plus a
selection policy in :func:`route` — callers are unaffected, they only ask for
``route(provider, action)``.
"""

import uuid
from enum import Enum
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException


class ToolAction(str, Enum):
    """A user-facing operation a tool can perform."""

    TEST_CONNECTION = "test_connection"
    EXTRACT = "extract"
    CREATE_TICKET = "create_ticket"


class Transport(str, Enum):
    """How an action is carried out."""

    REST = "rest"
    MCP = "mcp"


# (provider, action) -> transport. REST wherever a client exists. Actions a provider
# can only serve through the MCP agent (Transport.MCP) are registered the same way —
# that is how MCP-based providers (e.g. GitLab, Shortcut, Asana, Azure DevOps) plug in.
_ROUTES: Dict[Tuple[str, ToolAction], Transport] = {
    ("notion", ToolAction.EXTRACT): Transport.REST,
    ("notion", ToolAction.TEST_CONNECTION): Transport.REST,
    ("github", ToolAction.EXTRACT): Transport.REST,
    ("github", ToolAction.TEST_CONNECTION): Transport.REST,
    ("jira", ToolAction.TEST_CONNECTION): Transport.REST,
    ("jira", ToolAction.CREATE_TICKET): Transport.REST,
    ("confluence", ToolAction.TEST_CONNECTION): Transport.REST,
    ("gitlab", ToolAction.EXTRACT): Transport.MCP,
    ("gitlab", ToolAction.TEST_CONNECTION): Transport.MCP,
    ("shortcut", ToolAction.EXTRACT): Transport.MCP,
    ("shortcut", ToolAction.TEST_CONNECTION): Transport.MCP,
    ("asana", ToolAction.EXTRACT): Transport.MCP,
    ("asana", ToolAction.TEST_CONNECTION): Transport.MCP,
    ("azure_devops", ToolAction.EXTRACT): Transport.MCP,
    ("azure_devops", ToolAction.TEST_CONNECTION): Transport.MCP,
}


def route(provider: str, action: ToolAction) -> Transport:
    """Return the transport for *provider*/*action*.

    Raises:
        ToolConfigurationError: If the provider does not support the action.
    """
    transport = _ROUTES.get((provider, action))
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
            tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
        except ItemDeletedException:
            raise ToolConfigurationError(
                f"Tool '{tool_id}' has been deleted. Please re-import the source."
            )
        if not tool:
            raise ToolConfigurationError(f"Tool '{tool_id}' not found.")
        return tool.tool_provider_type.type_value

    provider_type = crud.get_type_lookup(db, provider_type_id, organization_id, user_id)
    if not provider_type:
        raise ToolConfigurationError(f"Provider type '{provider_type_id}' not found.")
    return provider_type.type_value
