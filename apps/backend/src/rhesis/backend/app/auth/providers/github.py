"""
GitHub OAuth Authentication Provider.

This provider handles authentication via GitHub's OAuth 2.0.
"""

import os
from typing import Any, Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request, status

from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.providers.base import AuthProvider, AuthUser
from rhesis.backend.logging import logger


class GitHubProvider(AuthProvider):
    """
    GitHub OAuth authentication provider.

    Implements GitHub Sign-In using OAuth 2.0.

    Environment variables:
        GH_CLIENT_ID: GitHub OAuth client ID (required to enable)
        GH_CLIENT_SECRET: GitHub OAuth client secret (required to enable)

    Setup:
        1. Go to https://github.com/settings/developers
        2. Click "New OAuth App" or "Register a new application"
        3. Fill in the application details:
           - Application name: Your app name
           - Homepage URL: Your app URL
           - Authorization callback URL: https://yourapp.com/auth/callback
        4. Copy the client ID and generate a client secret
        5. Set GH_CLIENT_ID and GH_CLIENT_SECRET environment variables

    Note:
        GitHub may not return an email if the user has set their email to private.
        In this case, we fetch the primary email from the emails endpoint.
    """

    def __init__(self):
        """Initialize the GitHub OAuth client."""
        self._oauth: Optional[OAuth] = None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "github"

    @property
    def display_name(self) -> str:
        """Return the display name for UI."""
        return "GitHub"

    @property
    def is_enabled(self) -> bool:
        """
        Check if GitHub OAuth is configured.

        Both GH_CLIENT_ID and GH_CLIENT_SECRET must be set.
        """
        return bool(os.getenv("GH_CLIENT_ID") and os.getenv("GH_CLIENT_SECRET"))

    @property
    def is_oauth(self) -> bool:
        """GitHub uses OAuth flow."""
        return True

    def _get_oauth(self) -> OAuth:
        """
        Get or create the OAuth client instance.

        Uses lazy initialization to avoid errors when credentials aren't set.
        """
        if self._oauth is None:
            self._oauth = OAuth()
            self._oauth.register(
                name="github",
                client_id=os.getenv("GH_CLIENT_ID"),
                client_secret=os.getenv("GH_CLIENT_SECRET"),
                access_token_url="https://github.com/login/oauth/access_token",
                authorize_url="https://github.com/login/oauth/authorize",
                api_base_url="https://api.github.com/",
                client_kwargs={
                    "scope": "user:email read:user",
                },
            )
        return self._oauth

    async def get_authorization_url(self, request: Request, redirect_uri: str) -> Any:
        """
        Get the GitHub authorization URL.

        Args:
            request: The FastAPI request object
            redirect_uri: The callback URL after authorization

        Returns:
            RedirectResponse to GitHub's authorization page
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub authentication is not configured",
            )

        oauth = self._get_oauth()
        return await oauth.github.authorize_redirect(request, redirect_uri)

    async def _get_primary_email(self, oauth: OAuth, token: dict) -> Optional[str]:
        """
        Fetch the user's primary email from GitHub's emails endpoint.

        GitHub users can have their email set to private, in which case
        we need to fetch it separately from the /user/emails endpoint.

        Args:
            oauth: The OAuth client instance
            token: The access token

        Returns:
            The user's primary email, or None if not found
        """
        try:
            resp = await oauth.github.get("user/emails", token=token)
            emails = resp.json()

            # Find primary email
            for email_data in emails:
                if email_data.get("primary") and email_data.get("verified"):
                    return email_data.get("email")

            # Fallback to first verified email
            for email_data in emails:
                if email_data.get("verified"):
                    return email_data.get("email")

            # Last resort: any email
            if emails:
                return emails[0].get("email")

        except Exception as e:
            logger.warning(f"Failed to fetch GitHub emails: {e}")

        return None

    async def authenticate(self, request: Request, **kwargs) -> AuthUser:
        """
        Authenticate user after GitHub OAuth callback.

        Args:
            request: The FastAPI request object containing OAuth callback data
            **kwargs: Additional arguments (ignored)

        Returns:
            AuthUser with the authenticated user's information

        Raises:
            HTTPException: If authentication fails
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub authentication is not configured",
            )

        try:
            oauth = self._get_oauth()
            token = await oauth.github.authorize_access_token(request)

            # Get user info from GitHub API
            resp = await oauth.github.get("user", token=token)
            userinfo = resp.json()

            if not userinfo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user information from GitHub",
                )

            # Get email - may need to fetch separately if private
            email = userinfo.get("email")
            if not email:
                email = await self._get_primary_email(oauth, token)

            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Could not retrieve email from GitHub. "
                        "Please make sure you have a verified email on your GitHub account."
                    ),
                )

            # Parse name
            name = userinfo.get("name") or userinfo.get("login")
            given_name = None
            family_name = None

            if name and " " in name:
                parts = name.split(" ", 1)
                given_name = parts[0]
                family_name = parts[1] if len(parts) > 1 else None

            logger.info(f"Successful GitHub OAuth login for: {email}")

            return AuthUser(
                provider_type=AuthProviderType.GITHUB,
                external_id=str(userinfo.get("id")),
                email=email,
                name=name,
                given_name=given_name,
                family_name=family_name,
                picture=userinfo.get("avatar_url"),
                raw_data=userinfo,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GitHub OAuth error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub authentication failed: {str(e)}",
            )
