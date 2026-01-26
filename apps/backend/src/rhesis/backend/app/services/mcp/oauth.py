"""OAuth 2.0 implementation for MCP servers.

This module provides OAuth 2.0 Authorization Code Grant (3LO) support for MCP servers,
starting with Atlassian. It includes configuration classes, service functions for token
management, and router handler functions.
"""

import json
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.tool import Tool
from rhesis.backend.app.schemas.tool import ToolUpdate
from rhesis.backend.logging import logger

# ============================================================================
# OAuth Configuration Classes
# ============================================================================


@dataclass
class MCPOAuthConfig:
    """Generic OAuth configuration for MCP providers."""

    client_id: str
    client_secret: str
    token_url: str
    authorize_url: str
    scopes: List[str]
    grant_type: str = "authorization_code"
    audience: Optional[str] = None
    prompt: Optional[str] = None


@dataclass
class AtlassianOAuthConfig(MCPOAuthConfig):
    """Atlassian-specific OAuth 2.0 (3LO) configuration."""

    def __init__(self):
        client_id = os.getenv("ATLASSIAN_OAUTH_CLIENT_ID")
        client_secret = os.getenv("ATLASSIAN_OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ValueError(
                "ATLASSIAN_OAUTH_CLIENT_ID and ATLASSIAN_OAUTH_CLIENT_SECRET "
                "environment variables must be set"
            )

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            token_url="https://auth.atlassian.com/oauth/token",
            authorize_url="https://auth.atlassian.com/authorize",
            scopes=[
                "read:jira-work",
                "write:jira-work",
                "read:confluence-content.all",
                "offline_access",
            ],
            grant_type="authorization_code",
            audience="api.atlassian.com",
            prompt="consent",
        )


# ============================================================================
# Public OAuth Functions (called by routers)
# ============================================================================


async def authorize_mcp_oauth(
    validate: bool,
    tool_id: Optional[uuid.UUID],
    provider: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """
    Initiate OAuth 2.0 Authorization Code flow.

    Routes to validation or normal mode based on validate flag.
    """
    if validate:
        return await _authorize_validation(provider, organization_id, user_id)
    else:
        if not tool_id:
            raise HTTPException(status_code=400, detail="tool_id required for normal OAuth flow")
        return await _authorize_normal(tool_id, provider, db, organization_id, user_id)


async def callback_mcp_oauth(
    tool_id: Optional[uuid.UUID],
    code: str,
    state: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """
    Handle OAuth callback after user authorization.

    Routes to validation or normal mode based on state format.
    """
    # Parse mode from state
    try:
        mode = state.split(":")[0]
        if mode not in ["validate", "normal"]:
            raise ValueError(f"Invalid mode: {mode}")
    except (IndexError, ValueError) as e:
        logger.error(f"Failed to parse OAuth state: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid state format. Please retry authorization."
        )

    if mode == "validate":
        return await _callback_validation(code, state, organization_id, user_id)
    else:
        return await _callback_normal(tool_id, code, state, db, organization_id, user_id)


def is_oauth_token(credentials: dict) -> bool:
    """Check if credentials contain OAuth tokens."""
    return "ACCESS_TOKEN" in credentials and "REFRESH_TOKEN" in credentials


def is_token_expired(expires_at: str, buffer_minutes: int = 5) -> bool:
    """Check if token is expired or about to expire."""
    if not expires_at:
        return True

    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        buffer = timedelta(minutes=buffer_minutes)
        return now >= (expiry - buffer)
    except (ValueError, AttributeError):
        logger.warning(f"Invalid expires_at format: {expires_at}")
        return True


async def exchange_code_for_token(
    code: str, config: MCPOAuthConfig, redirect_uri: str, code_verifier: Optional[str] = None
) -> dict:
    """Exchange authorization code for access token."""
    payload = {
        "grant_type": config.grant_type,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    if code_verifier:
        payload["code_verifier"] = code_verifier

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.token_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Token exchange failed: {response.status_code} - {error_detail}")
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Failed to exchange authorization code for token: {response.status_code}"
                    ),
                )

            return response.json()
    except httpx.RequestError as e:
        logger.error(f"HTTP request failed during token exchange: {str(e)}")
        raise HTTPException(
            status_code=502, detail=f"Failed to connect to OAuth provider: {str(e)}"
        )


async def refresh_oauth_token(tool: Tool, credentials: dict, db: Session) -> dict:
    """Refresh expired OAuth tokens."""
    refresh_token = credentials.get("REFRESH_TOKEN")
    if not refresh_token:
        raise HTTPException(
            status_code=400, detail="No refresh token available. Please re-authenticate."
        )

    provider = tool.tool_provider_type.type_value
    if provider == "atlassian":
        config = AtlassianOAuthConfig()
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for provider: {provider}")

    payload = {
        "grant_type": "refresh_token",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "refresh_token": refresh_token,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.token_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Token refresh failed: {response.status_code} - {error_detail}")

                # Check for invalid grant error (expired/used refresh token)
                if response.status_code == 403 or "invalid_grant" in error_detail.lower():
                    raise HTTPException(
                        status_code=401,
                        detail=(
                            "Refresh token expired or invalid. "
                            "Please re-authenticate via the authorization flow."
                        ),
                    )

                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to refresh OAuth token: {response.status_code}",
                )

            token_data = response.json()

            expires_in = token_data.get("expires_in", 3600)
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

            updated_credentials = {
                "ACCESS_TOKEN": token_data["access_token"],
                "REFRESH_TOKEN": token_data.get("refresh_token", refresh_token),
                "EXPIRES_IN": expires_in,
                "EXPIRES_AT": expires_at,
                "SCOPES": token_data.get("scope", credentials.get("SCOPES", "")),
            }

            if "CLOUD_ID" in credentials:
                updated_credentials["CLOUD_ID"] = credentials["CLOUD_ID"]

            tool.credentials = json.dumps(updated_credentials)
            db.commit()
            db.refresh(tool)

            logger.info(f"Successfully refreshed OAuth token for tool {tool.id}")
            return updated_credentials

    except httpx.RequestError as e:
        logger.error(f"HTTP request failed during token refresh: {str(e)}")
        raise HTTPException(
            status_code=502, detail=f"Failed to connect to OAuth provider: {str(e)}"
        )


# ============================================================================
# Validation Mode (test connection without saving tool)
# ============================================================================


async def _authorize_validation(
    provider: str,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """Initiate OAuth validation flow (test connection)."""
    from rhesis.backend.app.services.connector.redis_client import redis_manager

    # Get OAuth config
    if provider == "atlassian":
        config = AtlassianOAuthConfig()
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for provider: {provider}")

    # Check Redis availability
    if not redis_manager.is_available:
        raise HTTPException(status_code=503, detail="Cache unavailable. Please try again later.")

    # Generate state
    state = f"validate:{secrets.token_urlsafe(32)}"

    # Store state in Redis
    cache_key = f"oauth_state:{state}"
    state_data = {
        "provider": provider,
        "organization_id": organization_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }

    try:
        await redis_manager.client.setex(cache_key, 600, json.dumps(state_data))
    except Exception as e:
        logger.error(f"Failed to store OAuth state in Redis: {e}")
        raise HTTPException(
            status_code=503, detail="Failed to initialize OAuth flow. Please try again."
        )

    # Build authorization URL
    base_url = os.getenv("RHESIS_BASE_URL", "http://localhost:8080")
    redirect_uri = f"{base_url}/services/mcp/auth/callback"

    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
    }

    if config.audience:
        params["audience"] = config.audience
    if config.prompt:
        params["prompt"] = config.prompt

    authorization_url = f"{config.authorize_url}?{urlencode(params)}"

    logger.info(f"Redirecting to {provider} OAuth authorization (validation mode)")
    return RedirectResponse(url=authorization_url)


async def _callback_validation(
    code: str,
    state: str,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """Handle OAuth callback for validation flow."""
    from rhesis.backend.app.services.connector.redis_client import redis_manager

    if not redis_manager.is_available:
        raise HTTPException(status_code=503, detail="Cache unavailable.")

    # Retrieve state from Redis
    cache_key = f"oauth_state:{state}"
    try:
        state_data_str = await redis_manager.client.get(cache_key)
    except Exception as e:
        logger.error(f"Failed to retrieve OAuth state from Redis: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve OAuth state. Please retry.")

    if not state_data_str:
        raise HTTPException(
            status_code=400, detail="OAuth state not found or expired. Please retry authorization."
        )

    try:
        state_data = json.loads(state_data_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse state data: {e}")
        raise HTTPException(status_code=500, detail="Invalid state data. Please retry.")

    # Check expiry
    expires_at = state_data.get("expires_at")
    if expires_at and is_token_expired(expires_at, buffer_minutes=0):
        await redis_manager.client.delete(cache_key)
        raise HTTPException(status_code=400, detail="OAuth state expired. Please retry.")

    provider = state_data.get("provider")

    # Get config
    if provider == "atlassian":
        config = AtlassianOAuthConfig()
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for provider: {provider}")

    # Exchange code for tokens
    base_url = os.getenv("RHESIS_BASE_URL", "http://localhost:8080")
    redirect_uri = f"{base_url}/services/mcp/auth/callback"
    token_data = await exchange_code_for_token(code, config, redirect_uri)

    # Build credentials
    expires_in = token_data.get("expires_in", 3600)
    expires_at_timestamp = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    credentials = {
        "ACCESS_TOKEN": token_data["access_token"],
        "REFRESH_TOKEN": token_data.get("refresh_token", ""),
        "EXPIRES_IN": expires_in,
        "EXPIRES_AT": expires_at_timestamp,
        "SCOPES": token_data.get("scope", " ".join(config.scopes)),
    }

    # Get provider-specific data
    provider_data = await _get_provider_data(provider, credentials["ACCESS_TOKEN"])
    credentials.update(provider_data["credentials"])

    # Store validation result
    session_id = secrets.token_urlsafe(32)
    result_key = f"oauth_validation_result:{session_id}"
    result_data = {
        "provider": provider,
        "credentials": credentials,
        "site_name": provider_data.get("site_name"),
        "site_url": provider_data.get("site_url"),
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await redis_manager.client.setex(result_key, 300, json.dumps(result_data))
    except Exception as e:
        logger.error(f"Failed to store validation result: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to store validation result. Please retry."
        )

    # Clean up state
    await redis_manager.client.delete(cache_key)

    # Redirect to frontend
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    success_url = f"{frontend_url}/integrations/tools?oauth_validation=success&session={session_id}"

    logger.info(f"Validation OAuth completed successfully (session: {session_id})")
    return RedirectResponse(url=success_url)


# ============================================================================
# Normal Mode (save credentials to existing tool)
# ============================================================================


async def _authorize_normal(
    tool_id: uuid.UUID,
    provider: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """Initiate OAuth normal flow (save to tool)."""
    # Get tool
    tool = crud.get_tool(db, tool_id, organization_id, user_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    # Get OAuth config
    if provider == "atlassian":
        config = AtlassianOAuthConfig()
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for provider: {provider}")

    # Generate state
    state = f"normal:{secrets.token_urlsafe(32)}:{tool_id}"

    # Store state in tool metadata
    tool_metadata = tool.tool_metadata or {}
    tool_metadata["oauth_state"] = {
        "state": state,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }

    tool_update = ToolUpdate(tool_metadata=tool_metadata)
    crud.update_tool(db, tool_id, tool_update, organization_id, user_id)

    # Build authorization URL
    base_url = os.getenv("RHESIS_BASE_URL", "http://localhost:8080")
    redirect_uri = f"{base_url}/services/mcp/auth/callback"

    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
    }

    if config.audience:
        params["audience"] = config.audience
    if config.prompt:
        params["prompt"] = config.prompt

    authorization_url = f"{config.authorize_url}?{urlencode(params)}"

    logger.info(f"Redirecting to {provider} OAuth authorization (tool {tool_id})")
    return RedirectResponse(url=authorization_url)


async def _callback_normal(
    tool_id: Optional[uuid.UUID],
    code: str,
    state: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """Handle OAuth callback for normal flow."""
    # Extract tool_id from state
    try:
        parts = state.split(":")
        tool_id_from_state = uuid.UUID(parts[2])
    except (IndexError, ValueError) as e:
        logger.error(f"Failed to extract tool_id from state: {e}")
        raise HTTPException(status_code=400, detail="Invalid state format - missing tool_id.")

    # Validate tool_id matches
    if tool_id and tool_id != tool_id_from_state:
        logger.warning(f"tool_id mismatch: param={tool_id}, state={tool_id_from_state}")
        raise HTTPException(status_code=400, detail="tool_id mismatch.")

    tool_id = tool_id_from_state

    # Get tool
    tool = crud.get_tool(db, tool_id, organization_id, user_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    # Validate state
    metadata = tool.tool_metadata or {}
    oauth_state = metadata.get("oauth_state", {})

    if not oauth_state:
        raise HTTPException(
            status_code=400, detail="No OAuth state found. Please retry authorization."
        )

    stored_state = oauth_state.get("state")
    if state != stored_state:
        raise HTTPException(
            status_code=400, detail="Invalid state parameter. Possible CSRF attack."
        )

    expires_at = oauth_state.get("expires_at")
    if expires_at and is_token_expired(expires_at, buffer_minutes=0):
        raise HTTPException(status_code=400, detail="OAuth state expired. Please retry.")

    # Get provider and config
    provider = tool.tool_provider_type.type_value

    if provider == "atlassian":
        config = AtlassianOAuthConfig()
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for provider: {provider}")

    # Exchange code for tokens
    base_url = os.getenv("RHESIS_BASE_URL", "http://localhost:8080")
    redirect_uri = f"{base_url}/services/mcp/auth/callback"
    token_data = await exchange_code_for_token(code, config, redirect_uri)

    # Build credentials
    expires_in = token_data.get("expires_in", 3600)
    expires_at_timestamp = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    credentials = {
        "ACCESS_TOKEN": token_data["access_token"],
        "REFRESH_TOKEN": token_data.get("refresh_token", ""),
        "EXPIRES_IN": expires_in,
        "EXPIRES_AT": expires_at_timestamp,
        "SCOPES": token_data.get("scope", " ".join(config.scopes)),
    }

    # Get provider-specific data
    provider_data = await _get_provider_data(provider, credentials["ACCESS_TOKEN"])
    credentials.update(provider_data["credentials"])

    # Update tool
    tool.credentials = json.dumps(credentials)

    # Clear OAuth state
    if "oauth_state" in metadata:
        del metadata["oauth_state"]
        tool.tool_metadata = metadata

    db.commit()
    db.refresh(tool)

    logger.info(f"Successfully completed OAuth flow for tool {tool_id}")

    # Redirect to frontend
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    success_url = f"{frontend_url}/integrations/tools?oauth_success=true&tool_id={tool_id}"

    return RedirectResponse(url=success_url)


# ============================================================================
# Provider-Specific Data Retrieval
# ============================================================================


async def _get_provider_data(provider: str, access_token: str) -> Dict[str, Any]:
    """
    Get provider-specific data after OAuth token exchange.

    For Atlassian: Fetches cloud_id from accessible-resources endpoint.
    For other providers: Add elif statements as needed.

    Returns:
        Dict with credentials (extra fields to merge), site_name, site_url
    """
    if provider == "atlassian":
        return await _get_atlassian_data(access_token)
    else:
        return {"credentials": {}}


async def _get_atlassian_data(access_token: str) -> Dict[str, Any]:
    """Get Atlassian cloud_id and site information."""
    url = "https://api.atlassian.com/oauth/token/accessible-resources"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to get Atlassian accessible resources: "
                    f"{response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to get Atlassian accessible resources: {response.status_code}",
                )

            resources = response.json()

    except httpx.RequestError as e:
        logger.error(f"HTTP request failed when getting accessible resources: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to Atlassian API: {str(e)}")

    if not resources or len(resources) == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No accessible Atlassian sites found. "
                "Please ensure you have access to at least one Jira or Confluence site."
            ),
        )

    site = resources[0]
    cloud_id = site["id"]
    site_name = site.get("name", "Unknown Site")
    site_url = site.get("url", "")

    logger.info(f"Retrieved Atlassian site: {site_name} (cloud_id: {cloud_id})")

    return {
        "credentials": {"CLOUD_ID": cloud_id},
        "site_name": site_name,
        "site_url": site_url,
    }
