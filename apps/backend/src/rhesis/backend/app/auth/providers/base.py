"""
Base classes for authentication providers.

This module defines the abstract base class and data structures that all
authentication providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fastapi import Request

from rhesis.backend.app.auth.constants import AuthProviderType


@dataclass
class AuthUser:
    """
    Normalized user data from any authentication provider.

    This dataclass provides a consistent interface for user information
    regardless of the authentication provider used. All providers must
    return an AuthUser instance upon successful authentication.

    Attributes:
        provider_type: The authentication provider type (see AuthProviderType enum)
        external_id: The unique identifier from the external provider (e.g., Google's sub claim)
        email: The user's email address (primary identifier for user matching)
        name: The user's full display name
        given_name: The user's first/given name
        family_name: The user's last/family name
        picture: URL to the user's profile picture
        raw_data: Original response data from the provider (for debugging/auditing)
    """

    provider_type: AuthProviderType
    external_id: str
    email: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate required fields after initialization."""
        if not self.provider_type:
            raise ValueError("provider_type is required")
        if not self.email:
            raise ValueError("email is required")

    @property
    def display_name(self) -> str:
        """Return the best available display name."""
        if self.name:
            return self.name
        full_name = f"{self.given_name or ''} {self.family_name or ''}".strip()
        return full_name or self.email


class AuthProvider(ABC):
    """
    Abstract base class for authentication providers.

    All authentication providers must extend this class and implement
    the required abstract methods. The provider registry uses these
    methods to manage authentication flows.

    Example implementation:

        class GoogleProvider(AuthProvider):
            name = "google"
            display_name = "Google"

            @property
            def is_enabled(self) -> bool:
                return bool(os.getenv("GOOGLE_CLIENT_ID"))

            async def authenticate(self, request: Request, **kwargs) -> AuthUser:
                # ... OAuth flow implementation ...
                return AuthUser(
                    provider_type=AuthProviderType.GOOGLE,
                    external_id=userinfo["sub"],
                    email=userinfo["email"],
                    name=userinfo.get("name"),
                )
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this provider.

        This is used in URLs (e.g., /auth/login/google) and database storage.
        Should be lowercase, alphanumeric, no spaces.

        Returns:
            Provider name (e.g., 'google', 'github', 'email')
        """
        pass

    @property
    def display_name(self) -> str:
        """
        Human-readable name for this provider.

        Used in UI elements like login buttons.

        Returns:
            Display name (e.g., 'Google', 'GitHub', 'Email')
        """
        return self.name.title()

    @property
    @abstractmethod
    def is_enabled(self) -> bool:
        """
        Check if this provider is configured and enabled.

        Providers should check for required environment variables
        and return False if not properly configured.

        Returns:
            True if provider is ready to use, False otherwise
        """
        pass

    @property
    def is_oauth(self) -> bool:
        """
        Check if this provider uses OAuth/OIDC flow.

        OAuth providers require redirect-based authentication,
        while credential providers (email/password, LDAP) use
        direct authentication.

        Returns:
            True for OAuth providers, False for credential providers
        """
        return True  # Default to OAuth, override for credential providers

    @abstractmethod
    async def authenticate(self, request: Request, **kwargs) -> AuthUser:
        """
        Authenticate a user and return normalized user data.

        For OAuth providers, this is called after the OAuth callback
        to exchange the authorization code for user information.

        For credential providers (email/password), this validates
        the provided credentials directly.

        Args:
            request: The FastAPI request object
            **kwargs: Provider-specific arguments (e.g., email, password for email provider)

        Returns:
            AuthUser with normalized user information

        Raises:
            HTTPException: If authentication fails
            ValueError: If credentials are invalid
        """
        pass

    async def get_authorization_url(self, request: Request, redirect_uri: str) -> Any:
        """
        Get the authorization URL for OAuth providers.

        This method initiates the OAuth flow by returning a redirect
        response to the provider's authorization endpoint.

        Args:
            request: The FastAPI request object
            redirect_uri: The callback URL after authorization

        Returns:
            RedirectResponse to the provider's authorization page

        Raises:
            NotImplementedError: If called on a non-OAuth provider
        """
        if not self.is_oauth:
            raise NotImplementedError(
                f"Provider '{self.name}' does not support OAuth authorization flow"
            )
        raise NotImplementedError(
            f"OAuth provider '{self.name}' must implement get_authorization_url()"
        )

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider information for API responses.

        Returns:
            Dictionary with provider metadata for frontend consumption
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "type": "oauth" if self.is_oauth else "credentials",
            "enabled": self.is_enabled,
        }
