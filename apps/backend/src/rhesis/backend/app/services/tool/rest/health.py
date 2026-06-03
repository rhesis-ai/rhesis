"""Lightweight REST health checks for tool providers."""

import json
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp.exceptions import MCPConfigurationError

from .config import build_client


async def run_rest_health_check(
    db: Session,
    organization_id: str,
    tool_id: Optional[str] = None,
    provider_type_id: Optional[uuid.UUID] = None,
    credentials: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Test a tool's credentials via a lightweight REST health check.

    Accepts either an existing tool_id (loads credentials from DB) or
    provider_type_id + credentials (tests without saving).
    """
    if tool_id is not None:
        try:
            tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
        except ItemDeletedException:
            raise MCPConfigurationError(f"Tool '{tool_id}' has been deleted.")
        if not tool:
            raise MCPConfigurationError(f"Tool '{tool_id}' not found.")

        provider = tool.tool_provider_type.type_value
        try:
            credentials = json.loads(tool.credentials)
        except (json.JSONDecodeError, TypeError) as e:
            raise MCPConfigurationError(f"Invalid credentials for tool '{tool_id}': {e}")
    else:
        provider_type = crud.get_type_lookup(db, provider_type_id, organization_id, user_id)
        if not provider_type:
            raise MCPConfigurationError(f"Provider type '{provider_type_id}' not found.")
        provider = provider_type.type_value

    return await build_client(provider, credentials or {}).health_check()
