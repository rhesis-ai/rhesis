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
    """Atlassian-specific OAuth 2.0 (3LO) configuration.

    Atlassian uses Authorization Code Grant, NOT client credentials.
    Requires user interaction to authorize the app.

    Critical requirements:
    - audience: Must be "api.atlassian.com"
    - prompt: Must be "consent" to show authorization screen
    - offline_access scope: Required to get refresh token
    - cloud_id: Required from accessible-resources endpoint for API URLs
    """

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
            audience="api.atlassian.com",  # Required for Atlassian
            prompt="consent",  # Required to show consent screen
        )


# ============================================================================
# OAuth Service Functions
# ============================================================================


def is_oauth_token(credentials: dict) -> bool:
    """Check if credentials contain OAuth tokens.

    Args:
        credentials: Credentials dictionary

    Returns:
        True if credentials contain OAuth tokens (ACCESS_TOKEN and REFRESH_TOKEN)
    """
    return "ACCESS_TOKEN" in credentials and "REFRESH_TOKEN" in credentials


def is_token_expired(expires_at: str, buffer_minutes: int = 5) -> bool:
    """Check if token is expired or about to expire.

    Args:
        expires_at: ISO 8601 timestamp string
        buffer_minutes: Refresh token this many minutes before expiry

    Returns:
        True if token is expired or will expire within buffer_minutes
    """
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
    """Exchange authorization code for access token.

    Args:
        code: Authorization code from OAuth callback
        config: OAuth configuration
        redirect_uri: Redirect URI used in authorization request
        code_verifier: PKCE code verifier (optional)

    Returns:
        Token response dict with access_token, refresh_token, expires_in, scope

    Raises:
        HTTPException: If token exchange fails
    """
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


async def get_accessible_resources(access_token: str) -> list:
    """Get Atlassian accessible resources (REQUIRED).

    This step is MANDATORY after getting access token.
    Returns list of Atlassian sites the user has access to, including the cloud_id
    which is needed to construct API URLs.

    Endpoint: GET https://api.atlassian.com/oauth/token/accessible-resources

    Args:
        access_token: OAuth access token

    Returns:
        List of accessible resources with cloud_id, name, url, scopes, avatarUrl

    Example response:
        [
          {
            "id": "1324a887-45db-1bf4-1e99-ef0ff456d421",  // This is the cloud_id
            "name": "Site name",
            "url": "https://your-domain.atlassian.net",
            "scopes": ["write:jira-work", "read:jira-user", ...],
            "avatarUrl": "https://..."
          }
        ]

    Raises:
        HTTPException: If request fails
    """
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
                    f"Failed to get accessible resources: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Failed to get Atlassian accessible resources: {response.status_code}"
                    ),
                )

            return response.json()
    except httpx.RequestError as e:
        logger.error(f"HTTP request failed when getting accessible resources: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to Atlassian API: {str(e)}")


async def refresh_oauth_token(tool: Tool, credentials: dict, db: Session) -> dict:
    """Refresh expired OAuth tokens.

    CRITICAL: Atlassian uses ROTATING refresh tokens.
    Each successful refresh:
    1. Returns a NEW access_token and NEW refresh_token
    2. Invalidates the OLD refresh_token immediately
    3. You MUST update the database with the new refresh_token
    4. Reuse interval: 10 minutes (grace period for network issues)
    5. Inactivity expiry: 90 days

    Args:
        tool: Tool model instance
        credentials: Current credentials dict with REFRESH_TOKEN
        db: Database session

    Returns:
        Updated credentials dict with new tokens

    Raises:
        HTTPException: If refresh fails
    """
    refresh_token = credentials.get("REFRESH_TOKEN")
    if not refresh_token:
        raise HTTPException(
            status_code=400, detail="No refresh token available. Please re-authenticate."
        )

    # Get provider-specific config
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

            # Calculate expires_at
            expires_in = token_data.get("expires_in", 3600)
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

            # Update credentials with new tokens
            updated_credentials = {
                "ACCESS_TOKEN": token_data["access_token"],
                "REFRESH_TOKEN": token_data.get(
                    "refresh_token", refresh_token
                ),  # Use new or fallback to old
                "EXPIRES_IN": expires_in,
                "EXPIRES_AT": expires_at,
                "SCOPES": token_data.get("scope", credentials.get("SCOPES", "")),
            }

            # Preserve CLOUD_ID if present (Atlassian-specific)
            if "CLOUD_ID" in credentials:
                updated_credentials["CLOUD_ID"] = credentials["CLOUD_ID"]

            # Update database with new tokens
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
# OAuth Router Handler Functions
# ============================================================================


async def authorize_mcp_oauth(
    tool_id: uuid.UUID,
    db: Session,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """Handle GET /services/mcp/auth/{tool_id}/authorize

    Initiates OAuth 2.0 Authorization Code flow:
    1. Verify tool exists and belongs to organization
    2. Get provider-specific OAuth config
    3. Generate state parameter (security token)
    4. Store state in tool metadata for validation
    5. Construct authorization URL with required parameters
    6. Redirect user to authorization URL

    Args:
        tool_id: Tool instance UUID
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID

    Returns:
        RedirectResponse to OAuth provider's authorization URL

    Raises:
        HTTPException: If tool not found or invalid provider
    """
    # Get tool from database
    tool = crud.get_tool(db, tool_id, organization_id, user_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    # Get provider type
    provider = tool.tool_provider_type.type_value

    # Get provider-specific config
    if provider == "atlassian":
        config = AtlassianOAuthConfig()
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for provider: {provider}")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Generate PKCE code_verifier (optional but recommended)
    # For now, we'll skip PKCE to simplify implementation
    # Can be added later if needed

    # Store state in tool metadata for validation
    metadata = tool.tool_metadata or {}
    metadata["oauth_state"] = {
        "state": state,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }

    # Update tool metadata
    tool_update = ToolUpdate(tool_metadata=metadata)
    crud.update_tool(db, tool_id, tool_update, organization_id, user_id)

    # Construct authorization URL
    base_url = os.getenv("RHESIS_BASE_URL", "http://localhost:8080")
    redirect_uri = f"{base_url}/services/mcp/auth/{tool_id}/callback"

    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
    }

    # Add provider-specific parameters
    if config.audience:
        params["audience"] = config.audience
    if config.prompt:
        params["prompt"] = config.prompt

    # Build query string
    authorization_url = f"{config.authorize_url}?{urlencode(params)}"

    logger.info(f"Redirecting to OAuth authorization URL for tool {tool_id}")
    return RedirectResponse(url=authorization_url)


async def callback_mcp_oauth(
    tool_id: uuid.UUID,
    code: str,
    state: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> RedirectResponse:
    """Handle GET /services/mcp/auth/{tool_id}/callback

    Handles OAuth callback after user authorization:
    1. Validate state parameter against stored value
    2. Exchange authorization code for tokens
    3. Get accessible resources to retrieve cloud_id (for Atlassian)
    4. Store tokens and cloud_id in database
    5. Redirect to success page

    Args:
        tool_id: Tool instance UUID
        code: Authorization code from OAuth provider
        state: State parameter for CSRF protection
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID

    Returns:
        RedirectResponse to success page

    Raises:
        HTTPException: If validation fails or token exchange fails
    """
    # Get tool from database
    tool = crud.get_tool(db, tool_id, organization_id, user_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    # Validate state parameter
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

    # Check state expiry
    expires_at = oauth_state.get("expires_at")
    if expires_at and is_token_expired(expires_at, buffer_minutes=0):
        raise HTTPException(
            status_code=400, detail="OAuth state expired. Please retry authorization."
        )

    # Get provider type
    provider = tool.tool_provider_type.type_value

    # Get provider-specific config
    if provider == "atlassian":
        config = AtlassianOAuthConfig()
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for provider: {provider}")

    # Exchange code for token
    base_url = os.getenv("RHESIS_BASE_URL", "http://localhost:8080")
    redirect_uri = f"{base_url}/services/mcp/auth/{tool_id}/callback"

    token_data = await exchange_code_for_token(code, config, redirect_uri)

    # Calculate expires_at
    expires_in = token_data.get("expires_in", 3600)
    expires_at_timestamp = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    # Build credentials dict
    credentials = {
        "ACCESS_TOKEN": token_data["access_token"],
        "REFRESH_TOKEN": token_data.get("refresh_token", ""),
        "EXPIRES_IN": expires_in,
        "EXPIRES_AT": expires_at_timestamp,
        "SCOPES": token_data.get("scope", " ".join(config.scopes)),
    }

    # For Atlassian: Get accessible resources to retrieve cloud_id
    if provider == "atlassian":
        resources = await get_accessible_resources(token_data["access_token"])

        if not resources or len(resources) == 0:
            raise HTTPException(
                status_code=400,
                detail="No accessible Atlassian sites found. Please ensure you have access.",
            )

        # Use first site's cloud_id (can be enhanced later for multi-site selection)
        cloud_id = resources[0]["id"]
        credentials["CLOUD_ID"] = cloud_id

        logger.info(f"Retrieved cloud_id {cloud_id} for Atlassian site: {resources[0].get('name')}")

    # Update tool credentials
    tool.credentials = json.dumps(credentials)

    # Clear OAuth state from metadata
    if "oauth_state" in metadata:
        del metadata["oauth_state"]
        tool.tool_metadata = metadata

    db.commit()
    db.refresh(tool)

    logger.info(f"Successfully completed OAuth flow for tool {tool_id}")

    # Redirect to success page (frontend will handle this)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    success_url = f"{frontend_url}/integrations/tools?oauth_success=true&tool_id={tool_id}"

    return RedirectResponse(url=success_url)


async def refresh_mcp_oauth_endpoint(
    tool_id: uuid.UUID,
    db: Session,
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Handle POST /services/mcp/auth/{tool_id}/refresh

    Manually refresh OAuth tokens for a tool.

    Atlassian uses ROTATING refresh tokens:
    - Each refresh returns a NEW refresh token
    - Old refresh token becomes INVALID
    - Must update stored refresh token with new one
    - Default expiry: 90 days of inactivity
    - Reuse interval: 10 minutes (for network concurrency)

    Args:
        tool_id: Tool instance UUID
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID

    Returns:
        Dict with success message and new expiry time

    Raises:
        HTTPException: If tool not found or refresh fails
    """
    # Get tool from database
    tool = crud.get_tool(db, tool_id, organization_id, user_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    # Parse credentials
    try:
        credentials = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid credentials format: {e}")

    # Check if OAuth token
    if not is_oauth_token(credentials):
        raise HTTPException(status_code=400, detail="Tool does not use OAuth authentication")

    # Refresh token
    updated_credentials = await refresh_oauth_token(tool, credentials, db)

    return {
        "success": True,
        "message": "OAuth token refreshed successfully",
        "expires_at": updated_credentials.get("EXPIRES_AT"),
    }
