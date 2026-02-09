"""
Provider Registry for Authentication Providers.

This module manages the registration and discovery of authentication providers.
Providers are automatically registered based on environment configuration.
"""

from typing import Any, Dict, List, Optional, Type

from rhesis.backend.app.auth.providers.base import AuthProvider
from rhesis.backend.logging import logger


class ProviderRegistry:
    """
    Registry of available authentication providers.

    Providers auto-register based on environment variables. To add a new provider:
    1. Create a class extending AuthProvider
    2. Add it to AVAILABLE_PROVIDERS list
    3. Configure required environment variables

    The registry is initialized once at application startup and provides
    methods to query enabled providers and retrieve specific providers.

    Example usage:
        # Initialize at startup
        ProviderRegistry.initialize()

        # Get all enabled providers
        providers = ProviderRegistry.get_enabled_providers()

        # Get a specific provider
        google = ProviderRegistry.get_provider("google")
        if google and google.is_enabled:
            # Use the provider
            pass
    """

    # All available provider classes - add new providers here
    # Import is deferred to avoid circular imports
    AVAILABLE_PROVIDERS: List[Type[AuthProvider]] = []

    # Initialized provider instances
    _providers: Dict[str, AuthProvider] = {}
    _initialized: bool = False

    @classmethod
    def _load_provider_classes(cls) -> List[Type[AuthProvider]]:
        """
        Load provider classes lazily to avoid circular imports.

        Returns:
            List of provider classes
        """
        # Import here to avoid circular imports at module load time
        from rhesis.backend.app.auth.providers.email import EmailProvider
        from rhesis.backend.app.auth.providers.github import GitHubProvider
        from rhesis.backend.app.auth.providers.google import GoogleProvider

        return [
            EmailProvider,  # Email/password - default, always available
            GoogleProvider,  # Google OAuth
            GitHubProvider,  # GitHub OAuth
            # Add future providers here:
            # MicrosoftEntraProvider,
            # SAMLProvider,
            # LDAPProvider,
        ]

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize all providers.

        This should be called once at application startup. It instantiates
        all provider classes and registers them in the registry.
        """
        if cls._initialized:
            logger.debug("ProviderRegistry already initialized, skipping")
            return

        cls._providers = {}
        provider_classes = cls._load_provider_classes()

        for provider_class in provider_classes:
            try:
                provider = provider_class()
                cls._providers[provider.name] = provider
                status = "enabled" if provider.is_enabled else "disabled"
                logger.info(f"Registered auth provider: {provider.name} ({status})")
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_class}: {e}")

        cls._initialized = True
        enabled_count = len(cls.get_enabled_providers())
        logger.info(
            f"ProviderRegistry initialized with {len(cls._providers)} providers "
            f"({enabled_count} enabled)"
        )

    @classmethod
    def reset(cls) -> None:
        """
        Reset the registry (mainly for testing).

        Clears all registered providers and resets initialization state.
        """
        cls._providers = {}
        cls._initialized = False

    @classmethod
    def get_provider(cls, name: str) -> Optional[AuthProvider]:
        """
        Get a provider by name.

        Args:
            name: The provider name (e.g., 'google', 'github', 'email')

        Returns:
            The provider instance if found, None otherwise
        """
        if not cls._initialized:
            cls.initialize()
        return cls._providers.get(name)

    @classmethod
    def get_enabled_providers(cls) -> List[AuthProvider]:
        """
        Get all enabled providers.

        Returns:
            List of providers that are configured and enabled
        """
        if not cls._initialized:
            cls.initialize()
        return [p for p in cls._providers.values() if p.is_enabled]

    @classmethod
    def get_enabled_oauth_providers(cls) -> List[AuthProvider]:
        """
        Get enabled OAuth providers only.

        Excludes credential-based providers like email/password and LDAP.

        Returns:
            List of enabled OAuth providers
        """
        return [p for p in cls.get_enabled_providers() if p.is_oauth]

    @classmethod
    def get_enabled_credential_providers(cls) -> List[AuthProvider]:
        """
        Get enabled credential-based providers only.

        Includes providers like email/password and LDAP that don't use OAuth.

        Returns:
            List of enabled credential providers
        """
        return [p for p in cls.get_enabled_providers() if not p.is_oauth]

    @classmethod
    def get_enabled_provider_names(cls) -> List[str]:
        """
        Get names of all enabled providers.

        Returns:
            List of provider names
        """
        return [p.name for p in cls.get_enabled_providers()]

    @classmethod
    def get_provider_info(cls) -> List[Dict[str, Any]]:
        """
        Get information about all enabled providers for API responses.

        Returns:
            List of provider info dictionaries for frontend consumption
        """
        return [p.get_provider_info() for p in cls.get_enabled_providers()]

    @classmethod
    def is_provider_enabled(cls, name: str) -> bool:
        """
        Check if a specific provider is enabled.

        Args:
            name: The provider name

        Returns:
            True if provider exists and is enabled, False otherwise
        """
        provider = cls.get_provider(name)
        return provider is not None and provider.is_enabled
