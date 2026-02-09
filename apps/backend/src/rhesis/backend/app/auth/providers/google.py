"""
Google OAuth Authentication Provider.

This provider handles authentication via Google's OAuth 2.0 / OpenID Connect.
"""

import os
from typing import Any, Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request, status

from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.providers.base import AuthProvider, AuthUser
from rhesis.backend.logging import logger


class GoogleProvider(AuthProvider):
    """
    Google OAuth authentication provider.

    Implements Google Sign-In using OAuth 2.0 and OpenID Connect.

    Environment variables:
        GOOGLE_CLIENT_ID: Google OAuth client ID (required to enable)
        GOOGLE_CLIENT_SECRET: Google OAuth client secret (required to enable)

    Setup:
        1. Go to https://console.cloud.google.com/
        2. Create a new project or select existing
        3. Enable the Google+ API
        4. Go to Credentials > Create Credentials > OAuth client ID
        5. Configure the OAuth consent screen
        6. Add authorized redirect URIs (e.g., https://yourapp.com/auth/callback)
        7. Copy the client ID and secret to environment variables
    """

    def __init__(self):
        """Initialize the Google OAuth client."""
        self._oauth: Optional[OAuth] = None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "google"

    @property
    def display_name(self) -> str:
        """Return the display name for UI."""
        return "Google"

    @property
    def is_enabled(self) -> bool:
        """
        Check if Google OAuth is configured.

        Both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set.
        """
        return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))

    @property
    def is_oauth(self) -> bool:
        """Google uses OAuth flow."""
        return True

    def _get_oauth(self) -> OAuth:
        """
        Get or create the OAuth client instance.

        Uses lazy initialization to avoid errors when credentials aren't set.
        """
        if self._oauth is None:
            self._oauth = OAuth()
            self._oauth.register(
                name="google",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                server_metadata_url=(
                    "https://accounts.google.com/.well-known/openid-configuration"
                ),
                client_kwargs={
                    "scope": "openid email profile",
                },
            )
        return self._oauth

    async def get_authorization_url(self, request: Request, redirect_uri: str) -> Any:
        """
        Get the Google authorization URL.

        Args:
            request: The FastAPI request object
            redirect_uri: The callback URL after authorization

        Returns:
            RedirectResponse to Google's authorization page
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google authentication is not configured",
            )

        oauth = self._get_oauth()
        return await oauth.google.authorize_redirect(
            request,
            redirect_uri,
            prompt="select_account",  # Always show account selector
        )

    async def authenticate(self, request: Request, **kwargs) -> AuthUser:
        """
        Authenticate user after Google OAuth callback.

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
                detail="Google authentication is not configured",
            )

        try:
            oauth = self._get_oauth()
            token = await oauth.google.authorize_access_token(request)

            # Get user info from the token (OIDC includes it)
            userinfo = token.get("userinfo")

            if not userinfo:
                # Fallback: fetch from userinfo endpoint
                userinfo = await oauth.google.userinfo(token=token)

            if not userinfo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user information from Google",
                )

            email = userinfo.get("email")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google account does not have an email address",
                )

            logger.info(f"Successful Google OAuth login for: {email}")

            return AuthUser(
                provider_type=AuthProviderType.GOOGLE,
                external_id=userinfo.get("sub"),
                email=email,
                name=userinfo.get("name"),
                given_name=userinfo.get("given_name"),
                family_name=userinfo.get("family_name"),
                picture=userinfo.get("picture"),
                raw_data=dict(userinfo),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Google OAuth error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google authentication failed: {str(e)}",
            )
