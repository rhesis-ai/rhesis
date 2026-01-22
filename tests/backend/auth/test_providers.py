"""
Unit tests for authentication providers.

Tests the base AuthProvider class, AuthUser dataclass, and individual
provider implementations (Email, Google, GitHub).
"""

import os
from unittest.mock import patch

import pytest
from faker import Faker

fake = Faker()


# =============================================================================
# AuthUser Tests
# =============================================================================


class TestAuthUser:
    """Tests for the AuthUser dataclass."""

    @pytest.mark.unit
    def test_auth_user_creation_with_required_fields(self):
        """Test AuthUser creation with only required fields."""
        from rhesis.backend.app.auth.providers.base import AuthUser

        auth_user = AuthUser(
            provider_type="google",
            external_id="google|123456",
            email="test@example.com",
        )

        assert auth_user.provider_type == "google"
        assert auth_user.external_id == "google|123456"
        assert auth_user.email == "test@example.com"
        assert auth_user.name is None
        assert auth_user.given_name is None
        assert auth_user.family_name is None
        assert auth_user.picture is None
        assert auth_user.raw_data == {}

    @pytest.mark.unit
    def test_auth_user_creation_with_all_fields(self):
        """Test AuthUser creation with all fields."""
        from rhesis.backend.app.auth.providers.base import AuthUser

        raw_data = {"sub": "123456", "email_verified": True}
        auth_user = AuthUser(
            provider_type="google",
            external_id="google|123456",
            email="test@example.com",
            name="Test User",
            given_name="Test",
            family_name="User",
            picture="https://example.com/photo.jpg",
            raw_data=raw_data,
        )

        assert auth_user.name == "Test User"
        assert auth_user.given_name == "Test"
        assert auth_user.family_name == "User"
        assert auth_user.picture == "https://example.com/photo.jpg"
        assert auth_user.raw_data == raw_data

    @pytest.mark.unit
    def test_auth_user_display_name_with_name(self):
        """Test display_name property when name is set."""
        from rhesis.backend.app.auth.providers.base import AuthUser

        auth_user = AuthUser(
            provider_type="email",
            external_id="email|1",
            email="test@example.com",
            name="Full Name",
        )

        assert auth_user.display_name == "Full Name"

    @pytest.mark.unit
    def test_auth_user_display_name_with_given_family(self):
        """Test display_name property when only given/family names are set."""
        from rhesis.backend.app.auth.providers.base import AuthUser

        auth_user = AuthUser(
            provider_type="email",
            external_id="email|1",
            email="test@example.com",
            given_name="First",
            family_name="Last",
        )

        assert auth_user.display_name == "First Last"

    @pytest.mark.unit
    def test_auth_user_display_name_fallback_to_email(self):
        """Test display_name property falls back to email."""
        from rhesis.backend.app.auth.providers.base import AuthUser

        auth_user = AuthUser(
            provider_type="email",
            external_id="email|1",
            email="test@example.com",
        )

        assert auth_user.display_name == "test@example.com"

    @pytest.mark.unit
    def test_auth_user_requires_provider_type(self):
        """Test that provider_type is required."""
        from rhesis.backend.app.auth.providers.base import AuthUser

        with pytest.raises(ValueError, match="provider_type is required"):
            AuthUser(
                provider_type="",
                external_id="123",
                email="test@example.com",
            )

    @pytest.mark.unit
    def test_auth_user_requires_email(self):
        """Test that email is required."""
        from rhesis.backend.app.auth.providers.base import AuthUser

        with pytest.raises(ValueError, match="email is required"):
            AuthUser(
                provider_type="email",
                external_id="123",
                email="",
            )


# =============================================================================
# EmailProvider Tests
# =============================================================================


class TestEmailProvider:
    """Tests for the EmailProvider class."""

    @pytest.mark.unit
    def test_email_provider_name(self):
        """Test EmailProvider has correct name."""
        from rhesis.backend.app.auth.providers.email import EmailProvider

        provider = EmailProvider()
        assert provider.name == "email"
        assert provider.display_name == "Email"

    @pytest.mark.unit
    def test_email_provider_is_not_oauth(self):
        """Test EmailProvider is not an OAuth provider."""
        from rhesis.backend.app.auth.providers.email import EmailProvider

        provider = EmailProvider()
        assert provider.is_oauth is False

    @pytest.mark.unit
    def test_email_provider_enabled_by_default(self):
        """Test EmailProvider is enabled by default."""
        from rhesis.backend.app.auth.providers.email import EmailProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = EmailProvider()
            assert provider.is_enabled is True

    @pytest.mark.unit
    def test_email_provider_can_be_disabled(self):
        """Test EmailProvider can be disabled via environment."""
        from rhesis.backend.app.auth.providers.email import EmailProvider

        with patch.dict(os.environ, {"AUTH_EMAIL_PASSWORD_ENABLED": "false"}):
            provider = EmailProvider()
            assert provider.is_enabled is False

    @pytest.mark.unit
    def test_email_provider_registration_enabled_by_default(self):
        """Test registration is enabled by default."""
        from rhesis.backend.app.auth.providers.email import EmailProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = EmailProvider()
            assert provider.is_registration_enabled is True

    @pytest.mark.unit
    def test_email_provider_registration_can_be_disabled(self):
        """Test registration can be disabled."""
        from rhesis.backend.app.auth.providers.email import EmailProvider

        with patch.dict(os.environ, {"AUTH_REGISTRATION_ENABLED": "false"}):
            provider = EmailProvider()
            assert provider.is_registration_enabled is False

    @pytest.mark.unit
    def test_email_provider_info_includes_registration(self):
        """Test provider info includes registration status."""
        from rhesis.backend.app.auth.providers.email import EmailProvider

        provider = EmailProvider()
        info = provider.get_provider_info()

        assert "registration_enabled" in info
        assert info["type"] == "credentials"


# =============================================================================
# GoogleProvider Tests
# =============================================================================


class TestGoogleProvider:
    """Tests for the GoogleProvider class."""

    @pytest.mark.unit
    def test_google_provider_name(self):
        """Test GoogleProvider has correct name."""
        from rhesis.backend.app.auth.providers.google import GoogleProvider

        provider = GoogleProvider()
        assert provider.name == "google"
        assert provider.display_name == "Google"

    @pytest.mark.unit
    def test_google_provider_is_oauth(self):
        """Test GoogleProvider is an OAuth provider."""
        from rhesis.backend.app.auth.providers.google import GoogleProvider

        provider = GoogleProvider()
        assert provider.is_oauth is True

    @pytest.mark.unit
    def test_google_provider_disabled_without_credentials(self):
        """Test GoogleProvider is disabled without credentials."""
        from rhesis.backend.app.auth.providers.google import GoogleProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = GoogleProvider()
            assert provider.is_enabled is False

    @pytest.mark.unit
    def test_google_provider_enabled_with_credentials(self):
        """Test GoogleProvider is enabled with credentials."""
        from rhesis.backend.app.auth.providers.google import GoogleProvider

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-client-id",
                "GOOGLE_CLIENT_SECRET": "test-client-secret",
            },
        ):
            provider = GoogleProvider()
            assert provider.is_enabled is True

    @pytest.mark.unit
    def test_google_provider_requires_both_credentials(self):
        """Test GoogleProvider requires both client ID and secret."""
        from rhesis.backend.app.auth.providers.google import GoogleProvider

        # Only client ID
        with patch.dict(
            os.environ,
            {"GOOGLE_CLIENT_ID": "test-client-id"},
            clear=True,
        ):
            provider = GoogleProvider()
            assert provider.is_enabled is False

        # Only client secret
        with patch.dict(
            os.environ,
            {"GOOGLE_CLIENT_SECRET": "test-client-secret"},
            clear=True,
        ):
            provider = GoogleProvider()
            assert provider.is_enabled is False


# =============================================================================
# GitHubProvider Tests
# =============================================================================


class TestGitHubProvider:
    """Tests for the GitHubProvider class."""

    @pytest.mark.unit
    def test_github_provider_name(self):
        """Test GitHubProvider has correct name."""
        from rhesis.backend.app.auth.providers.github import GitHubProvider

        provider = GitHubProvider()
        assert provider.name == "github"
        assert provider.display_name == "GitHub"

    @pytest.mark.unit
    def test_github_provider_is_oauth(self):
        """Test GitHubProvider is an OAuth provider."""
        from rhesis.backend.app.auth.providers.github import GitHubProvider

        provider = GitHubProvider()
        assert provider.is_oauth is True

    @pytest.mark.unit
    def test_github_provider_disabled_without_credentials(self):
        """Test GitHubProvider is disabled without credentials."""
        from rhesis.backend.app.auth.providers.github import GitHubProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = GitHubProvider()
            assert provider.is_enabled is False

    @pytest.mark.unit
    def test_github_provider_enabled_with_credentials(self):
        """Test GitHubProvider is enabled with credentials."""
        from rhesis.backend.app.auth.providers.github import GitHubProvider

        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test-client-id",
                "GITHUB_CLIENT_SECRET": "test-client-secret",
            },
        ):
            provider = GitHubProvider()
            assert provider.is_enabled is True

    @pytest.mark.unit
    def test_github_provider_requires_both_credentials(self):
        """Test GitHubProvider requires both client ID and secret."""
        from rhesis.backend.app.auth.providers.github import GitHubProvider

        # Only client ID
        with patch.dict(
            os.environ,
            {"GITHUB_CLIENT_ID": "test-client-id"},
            clear=True,
        ):
            provider = GitHubProvider()
            assert provider.is_enabled is False
