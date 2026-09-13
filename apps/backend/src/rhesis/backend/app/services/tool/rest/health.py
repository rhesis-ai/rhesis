"""Lightweight REST health checks for tool providers."""

import functools
import json
import uuid
from typing import Any, Dict, Optional, Tuple

import anyio
from sqlalchemy.orm import Session

from rhesis.backend.app.crud import tool as tool_crud
from rhesis.backend.app.crud import type_lookup as type_lookup_crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

from .config import build_client


def _resolve_health_check_target(
    db: Session,
    organization_id: str,
    tool_id: Optional[str] = None,
    provider_type_id: Optional[uuid.UUID] = None,
    credentials: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None,
    tool_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[Dict[str, str]], Optional[Dict[str, Any]]]:
    """Resolve ``(provider, credentials, tool_metadata)`` for a health check.

    Runs in a worker thread: the caller awaits an outbound HTTP call afterwards,
    so none of this may touch the session from the event loop.
    """
    metadata = tool_metadata
    if tool_id is not None:
        try:
            tool = tool_crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
        except ItemDeletedException:
            raise ToolConfigurationError(f"Tool '{tool_id}' has been deleted.")
        if not tool:
            raise ToolConfigurationError(f"Tool '{tool_id}' not found.")

        provider = tool.tool_provider_type.type_value
        try:
            credentials = json.loads(tool.credentials)
        except (json.JSONDecodeError, TypeError) as e:
            raise ToolConfigurationError(f"Invalid credentials for tool '{tool_id}': {e}")
        if metadata is None:
            metadata = tool.tool_metadata
    else:
        provider_type = type_lookup_crud.get_type_lookup(
            db, provider_type_id, organization_id, user_id
        )
        if not provider_type:
            raise ToolConfigurationError(f"Provider type '{provider_type_id}' not found.")
        provider = provider_type.type_value

    return provider, credentials, metadata


async def run_rest_health_check(
    db: Session,
    organization_id: str,
    tool_id: Optional[str] = None,
    provider_type_id: Optional[uuid.UUID] = None,
    credentials: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None,
    tool_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Test a tool's credentials via a lightweight REST health check.

    Accepts either an existing tool_id (loads credentials from DB) or
    provider_type_id + credentials (tests without saving).
    """
    provider, resolved_credentials, metadata = await anyio.to_thread.run_sync(
        functools.partial(
            _resolve_health_check_target,
            db,
            organization_id,
            tool_id=tool_id,
            provider_type_id=provider_type_id,
            credentials=credentials,
            user_id=user_id,
            tool_metadata=tool_metadata,
        )
    )

    return await build_client(provider, resolved_credentials or {}).health_check(
        tool_metadata=metadata
    )
