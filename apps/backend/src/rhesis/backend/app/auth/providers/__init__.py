"""
Authentication Providers Package

This package provides a provider-agnostic authentication system that supports
multiple authentication methods (OAuth, email/password, LDAP, SAML, etc.).

The architecture follows a plugin pattern where providers auto-register based
on environment configuration. To add a new provider:

1. Create a new file (e.g., `microsoft.py`) extending `AuthProvider`
2. Implement the required abstract methods
3. Add the provider class to `AVAILABLE_PROVIDERS` in `registry.py`
4. Configure the required environment variables

See EXTENDING-AUTH-PROVIDERS.md for detailed documentation.
"""

from rhesis.backend.app.auth.providers.base import AuthProvider, AuthUser
from rhesis.backend.app.auth.providers.registry import ProviderRegistry

__all__ = [
    "AuthProvider",
    "AuthUser",
    "ProviderRegistry",
]
