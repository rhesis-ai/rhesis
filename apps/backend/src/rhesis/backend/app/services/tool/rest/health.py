"""Lightweight REST health checks for tool providers."""

import json
import uuid
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.sdk.agents.mcp.exceptions import MCPConfigurationError

from .github import GitHubSource
from .notion import NotionSource


async def _jira_health_check(jira_url: str, username: str, api_token: str) -> Dict[str, Any]:
    url = jira_url.rstrip("/") + "/rest/api/3/myself"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, auth=(username, api_token))
    if resp.status_code == 200:
        display = resp.json().get("displayName", "")
        return {"is_authenticated": "Yes", "message": f"Connected as {display}"}
    return {"is_authenticated": "No", "message": f"Authentication failed: {resp.status_code}"}


async def _confluence_health_check(
    confluence_url: str, username: str, api_token: str
) -> Dict[str, Any]:
    url = confluence_url.rstrip("/") + "/wiki/rest/api/user/current"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, auth=(username, api_token))
    if resp.status_code == 200:
        display = resp.json().get("displayName", "")
        return {"is_authenticated": "Yes", "message": f"Connected as {display}"}
    return {"is_authenticated": "No", "message": f"Authentication failed: {resp.status_code}"}


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

    if provider == "notion":
        return await NotionSource(token=credentials.get("NOTION_TOKEN", "")).health_check()

    if provider == "github":
        return await GitHubSource(
            token=credentials.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
        ).health_check()

    if provider == "jira":
        return await _jira_health_check(
            jira_url=credentials.get("JIRA_URL", ""),
            username=credentials.get("JIRA_USERNAME", ""),
            api_token=credentials.get("JIRA_API_TOKEN", ""),
        )

    if provider == "confluence":
        return await _confluence_health_check(
            confluence_url=credentials.get("CONFLUENCE_URL", ""),
            username=credentials.get("CONFLUENCE_USERNAME", ""),
            api_token=credentials.get("CONFLUENCE_API_TOKEN", ""),
        )

    raise MCPConfigurationError(f"No health check available for provider '{provider}'")
