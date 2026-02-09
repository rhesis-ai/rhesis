"""
Unit tests for the ProviderRegistry.

Tests provider registration, discovery, and management functionality.
"""

import os
from unittest.mock import patch

import pytest


class TestProviderRegistry:
    """Tests for the ProviderRegistry class."""

    def setup_method(self):
        """Reset registry before each test."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        ProviderRegistry.reset()

    @pytest.mark.unit
    def test_registry_initializes_providers(self):
        """Test that registry initializes all available providers."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        ProviderRegistry.initialize()

        # Should have at least the email provider
        assert len(ProviderRegistry._providers) >= 1
        assert "email" in ProviderRegistry._providers

    @pytest.mark.unit
    def test_registry_only_initializes_once(self):
        """Test that registry only initializes once."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        ProviderRegistry.initialize()
        initial_providers = dict(ProviderRegistry._providers)

        ProviderRegistry.initialize()  # Second call should be no-op

        assert ProviderRegistry._providers == initial_providers

    @pytest.mark.unit
    def test_registry_reset(self):
        """Test that registry can be reset."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        ProviderRegistry.initialize()
        assert len(ProviderRegistry._providers) > 0

        ProviderRegistry.reset()

        assert len(ProviderRegistry._providers) == 0
        assert ProviderRegistry._initialized is False

    @pytest.mark.unit
    def test_get_provider_by_name(self):
        """Test getting a provider by name."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        provider = ProviderRegistry.get_provider("email")

        assert provider is not None
        assert provider.name == "email"

    @pytest.mark.unit
    def test_get_provider_unknown_returns_none(self):
        """Test getting an unknown provider returns None."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        provider = ProviderRegistry.get_provider("unknown_provider")

        assert provider is None

    @pytest.mark.unit
    def test_get_enabled_providers(self):
        """Test getting enabled providers."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        # Email is enabled by default
        enabled = ProviderRegistry.get_enabled_providers()

        assert len(enabled) >= 1
        assert all(p.is_enabled for p in enabled)

    @pytest.mark.unit
    def test_get_enabled_oauth_providers(self):
        """Test getting enabled OAuth providers only."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        oauth_providers = ProviderRegistry.get_enabled_oauth_providers()

        assert all(p.is_oauth for p in oauth_providers)

    @pytest.mark.unit
    def test_get_enabled_credential_providers(self):
        """Test getting enabled credential providers only."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        credential_providers = ProviderRegistry.get_enabled_credential_providers()

        assert all(not p.is_oauth for p in credential_providers)

    @pytest.mark.unit
    def test_get_enabled_provider_names(self):
        """Test getting names of enabled providers."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        names = ProviderRegistry.get_enabled_provider_names()

        assert isinstance(names, list)
        assert "email" in names  # Email is enabled by default

    @pytest.mark.unit
    def test_get_provider_info(self):
        """Test getting provider info for API responses."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        info = ProviderRegistry.get_provider_info()

        assert isinstance(info, list)
        assert len(info) >= 1

        # Check structure of provider info
        for provider_info in info:
            assert "name" in provider_info
            assert "display_name" in provider_info
            assert "type" in provider_info
            assert "enabled" in provider_info

    @pytest.mark.unit
    def test_is_provider_enabled(self):
        """Test checking if a provider is enabled."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        # Email is enabled by default
        assert ProviderRegistry.is_provider_enabled("email") is True

        # Unknown provider should return False
        assert ProviderRegistry.is_provider_enabled("unknown") is False

    @pytest.mark.unit
    def test_oauth_providers_disabled_without_credentials(self):
        """Test OAuth providers are disabled without credentials."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        with patch.dict(os.environ, {}, clear=True):
            ProviderRegistry.reset()
            ProviderRegistry.initialize()

            # Google and GitHub should not be enabled
            assert ProviderRegistry.is_provider_enabled("google") is False
            assert ProviderRegistry.is_provider_enabled("github") is False

    @pytest.mark.unit
    def test_oauth_providers_enabled_with_credentials(self):
        """Test OAuth providers are enabled with credentials."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-google-id",
                "GOOGLE_CLIENT_SECRET": "test-google-secret",
                "GH_CLIENT_ID": "test-github-id",
                "GH_CLIENT_SECRET": "test-github-secret",
            },
        ):
            ProviderRegistry.reset()
            ProviderRegistry.initialize()

            assert ProviderRegistry.is_provider_enabled("google") is True
            assert ProviderRegistry.is_provider_enabled("github") is True

    @pytest.mark.unit
    def test_email_provider_can_be_disabled(self):
        """Test email provider can be disabled via environment."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        with patch.dict(os.environ, {"AUTH_EMAIL_PASSWORD_ENABLED": "false"}):
            ProviderRegistry.reset()
            ProviderRegistry.initialize()

            assert ProviderRegistry.is_provider_enabled("email") is False

    @pytest.mark.unit
    def test_auto_initialize_on_get_provider(self):
        """Test registry auto-initializes when getting a provider."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry

        # Registry should be uninitialized after reset
        assert ProviderRegistry._initialized is False

        # Getting a provider should trigger initialization
        provider = ProviderRegistry.get_provider("email")

        assert ProviderRegistry._initialized is True
        assert provider is not None
