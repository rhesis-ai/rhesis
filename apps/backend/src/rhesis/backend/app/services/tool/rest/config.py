"""Resolve a DB tool to its REST client implementation via a provider registry."""

import json
import uuid
from typing import Dict

from sqlalchemy.orm import Session

from rhesis.backend.app.crud import tool as tool_crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.url_validation import validate_base_url  # noqa: F401
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

from .base import RestClient


def build_client(provider: str, credentials: Dict[str, str]) -> RestClient:
    """Instantiate the RestClient for *provider* using *credentials*.

    The factory comes from the provider's manifest, so a provider that serves
    an action over REST cannot be missing a client without the manifest test
    catching it.

    Raises:
        ToolConfigurationError: If *provider* has no REST client.
    """
    # Imported at call time: a manifest names its REST client class, so
    # importing the registry here at module level would close the loop
    # providers -> rest -> config -> providers.
    from rhesis.backend.app.services.tool.providers import get_manifest

    manifest = get_manifest(provider)
    if manifest is None or manifest.rest_client is None:
        raise ToolConfigurationError(f"No REST client registered for provider '{provider}'")
    return manifest.rest_client(credentials)


def get_rest_client(
    db: Session, tool_id: str, organization_id: str, user_id: str | None = None
) -> RestClient:
    """Resolve a DB tool to its REST client.

    Raises:
        ToolConfigurationError: If tool not found, deleted, or provider unsupported.
    """
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

    try:
        credentials = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise ToolConfigurationError(f"Invalid credentials for tool '{tool_id}': {e}")

    return build_client(tool.tool_provider_type.type_value, credentials)
