"""
Tests for Polyphemus delegation integration.

This module tests:
- Creating Polyphemus clients with delegation tokens
- Integration with LLM utilities
- Token passing to SDK
"""

import os
from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.config.settings import get_rhesis_settings
from rhesis.backend.app.models.user import User


class TestPolyphemusDelegation:
    """Test Polyphemus delegation token integration."""

    @pytest.fixture
    def test_user(self):
        """Create a mock user for testing."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.organization_id = "org-456"
        user.is_active = True
        user.is_verified = True
        return user

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    def test_delegation_call(self, mock_polyphemus_class, test_user):
        """Test calling Polyphemus with delegation token."""
        from rhesis.backend.app.utils.user_model_utils import _call_polyphemus_with_delegation

        # Call the function
        _call_polyphemus_with_delegation(test_user, "default")

        # Verify PolyphemusLLM was instantiated
        mock_polyphemus_class.assert_called_once()

        # Get the kwargs passed to PolyphemusLLM
        call_kwargs = mock_polyphemus_class.call_args[1]

        # Verify required parameters
        assert "api_key" in call_kwargs
        assert "model_name" in call_kwargs
        assert "base_url" in call_kwargs

        assert call_kwargs["model_name"] == "default"

        # Verify api_key is a JWT token (not rh-* format)
        api_key = call_kwargs["api_key"]
        assert isinstance(api_key, str)
        assert not api_key.startswith("rh-")
        assert len(api_key) > 50  # JWT tokens are much longer

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    def test_delegation_with_custom_url(self, mock_polyphemus_class, test_user):
        """Test delegation respects POLYPHEMUS_URL environment variable."""
        from rhesis.backend.app.utils.user_model_utils import _call_polyphemus_with_delegation

        test_url = "http://localhost:8000"
        with patch.dict(os.environ, {"DEFAULT_POLYPHEMUS_URL": test_url}):
            _call_polyphemus_with_delegation(test_user, "default")

            call_kwargs = mock_polyphemus_class.call_args[1]
            assert call_kwargs["base_url"] == test_url

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    def test_delegation_default_url(self, mock_polyphemus_class, test_user):
        """Test delegation uses default URL when not set."""
        from rhesis.backend.app.utils.user_model_utils import _call_polyphemus_with_delegation

        # Remove DEFAULT_POLYPHEMUS_URL if it exists
        with patch.dict(os.environ, {}, clear=False):
            if "DEFAULT_POLYPHEMUS_URL" in os.environ:
                del os.environ["DEFAULT_POLYPHEMUS_URL"]

            _call_polyphemus_with_delegation(test_user, "default")

            call_kwargs = mock_polyphemus_class.call_args[1]
            assert call_kwargs["base_url"] == "https://polyphemus.rhesis.ai"

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    def test_delegation_with_kwargs(self, mock_polyphemus_class, test_user):
        """Test delegation passes additional kwargs to PolyphemusLLM."""
        from rhesis.backend.app.utils.user_model_utils import _call_polyphemus_with_delegation

        custom_kwargs = {"temperature": 0.7, "max_tokens": 1000}

        _call_polyphemus_with_delegation(test_user, "default", **custom_kwargs)

        call_kwargs = mock_polyphemus_class.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 1000

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    @patch("rhesis.backend.app.auth.token_utils.create_service_delegation_token")
    def test_delegation_token_creation(self, mock_create_token, mock_polyphemus_class, test_user):
        """Test that delegation token is created with correct parameters."""
        from rhesis.backend.app.utils.user_model_utils import _call_polyphemus_with_delegation

        # Ensure user is active and verified
        test_user.is_active = True
        test_user.is_verified = True

        mock_token = "mock.jwt.token"
        mock_create_token.return_value = mock_token

        _call_polyphemus_with_delegation(test_user, "default")

        # Verify token creation was called correctly
        mock_create_token.assert_called_once_with(test_user, "polyphemus")

        # Verify the token was passed to PolyphemusLLM
        call_kwargs = mock_polyphemus_class.call_args[1]
        assert call_kwargs["api_key"] == mock_token

    def test_delegation_inactive_user(self, test_user):
        """Test that delegation fails for inactive users."""
        from rhesis.backend.app.utils.user_model_utils import _call_polyphemus_with_delegation

        test_user.is_active = False
        test_user.is_verified = True

        with pytest.raises(ValueError, match="User account is inactive"):
            _call_polyphemus_with_delegation(test_user, "default")

    def test_delegation_unverified_user(self, test_user):
        """Test that delegation fails for unverified users."""
        from rhesis.backend.app.utils.user_model_utils import _call_polyphemus_with_delegation

        test_user.is_active = True
        test_user.is_verified = False

        with pytest.raises(ValueError, match="User account is not verified"):
            _call_polyphemus_with_delegation(test_user, "default")


class TestPolyphemusModelConfiguration:
    """Test Polyphemus model configuration flow."""

    @pytest.fixture(autouse=True)
    def clean_rhesis_api_key(self, monkeypatch):
        """Ensure RHESIS_API_KEY is unset by default and settings cache is reset."""
        monkeypatch.delenv("RHESIS_API_KEY", raising=False)
        get_rhesis_settings.cache_clear()
        yield
        get_rhesis_settings.cache_clear()

    @pytest.fixture
    def test_user(self):
        """Create a mock user for testing."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.organization_id = "org-456"
        user.is_active = True
        user.is_verified = True
        return user

    @pytest.fixture
    def mock_polyphemus_model(self):
        """Create a mock Polyphemus model from database."""
        from rhesis.backend.app.models.model import Model

        model = Mock(spec=Model)
        model.id = "model-789"
        model.name = "Rhesis Polyphemus"
        model.model_name = "default"
        model.key = None  # No API key for system model
        model.provider_type = Mock()
        model.provider_type.type_value = "polyphemus"
        return model

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    @patch("rhesis.backend.app.utils.user_model_utils.crud.get_model")
    def test_polyphemus_model_uses_delegation(
        self, mock_get_model, mock_polyphemus_class, test_user, mock_polyphemus_model
    ):
        """Without a configured RHESIS_API_KEY, Polyphemus models without a stored
        API key use per-user delegation tokens (Rhesis-hosted/SaaS mode)."""
        from sqlalchemy.orm import Session

        from rhesis.backend.app.utils.user_model_utils import _fetch_and_configure_model

        # Setup mocks
        mock_db = Mock(spec=Session)
        mock_get_model.return_value = mock_polyphemus_model

        # Call the function
        _fetch_and_configure_model(
            db=mock_db,
            model_id="model-789",
            organization_id="org-456",
            default_model="gpt-4",
            user=test_user,
        )

        # Verify PolyphemusLLM was instantiated with delegation token
        mock_polyphemus_class.assert_called_once()
        call_kwargs = mock_polyphemus_class.call_args[1]

        # Verify delegation token was used (not None, not empty string)
        assert "api_key" in call_kwargs
        assert call_kwargs["api_key"] is not None
        assert len(call_kwargs["api_key"]) > 0
        # JWT tokens don't start with rh-
        assert not call_kwargs["api_key"].startswith("rh-")

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    @patch("rhesis.backend.app.utils.user_model_utils.crud.get_model")
    @patch("rhesis.backend.app.utils.user_model_utils._call_polyphemus_with_delegation")
    def test_polyphemus_model_prefers_env_api_key_over_delegation(
        self,
        mock_delegate,
        mock_get_model,
        mock_polyphemus_class,
        test_user,
        mock_polyphemus_model,
        monkeypatch,
    ):
        """A configured RHESIS_API_KEY (self-hosted mode) takes precedence over
        minting a delegation token, even when a user is available."""
        from sqlalchemy.orm import Session

        from rhesis.backend.app.utils.user_model_utils import _fetch_and_configure_model

        monkeypatch.setenv("RHESIS_API_KEY", "rh-self-hosted-key")
        get_rhesis_settings.cache_clear()

        mock_db = Mock(spec=Session)
        mock_get_model.return_value = mock_polyphemus_model

        _fetch_and_configure_model(
            db=mock_db,
            model_id="model-789",
            organization_id="org-456",
            default_model="gpt-4",
            user=test_user,
        )

        # Delegation must not be used when a real API key is configured
        mock_delegate.assert_not_called()

        # PolyphemusLLM is reached via the generic SDK factory path, with
        # api_key=None so the SDK provider picks up RHESIS_API_KEY itself
        mock_polyphemus_class.assert_called_once()
        call_kwargs = mock_polyphemus_class.call_args[1]
        assert call_kwargs["api_key"] is None

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    @patch("rhesis.backend.app.utils.user_model_utils.crud.get_model")
    @patch("rhesis.backend.app.utils.user_model_utils._call_polyphemus_with_delegation")
    def test_polyphemus_model_uses_env_api_key_without_user(
        self,
        mock_delegate,
        mock_get_model,
        mock_polyphemus_class,
        mock_polyphemus_model,
        monkeypatch,
    ):
        """A configured RHESIS_API_KEY resolves the model even with no user
        available (e.g. background jobs), without requiring delegation."""
        from sqlalchemy.orm import Session

        from rhesis.backend.app.utils.user_model_utils import _fetch_and_configure_model

        monkeypatch.setenv("RHESIS_API_KEY", "rh-self-hosted-key")
        get_rhesis_settings.cache_clear()

        mock_db = Mock(spec=Session)
        mock_get_model.return_value = mock_polyphemus_model

        _fetch_and_configure_model(
            db=mock_db,
            model_id="model-789",
            organization_id="org-456",
            default_model="gpt-4",
            user=None,
        )

        mock_delegate.assert_not_called()
        mock_polyphemus_class.assert_called_once()


class TestModelEndpointConfiguration:
    """Test that stored model endpoint URLs are passed to the SDK."""

    @pytest.fixture
    def mock_db_model(self):
        from rhesis.backend.app.models.model import Model

        model = Mock(spec=Model)
        model.id = "model-789"
        model.name = "Local LiteLLM Proxy"
        model.model_name = "gemini"
        model.key = "test-key"
        model.endpoint = "http://host.docker.internal:4000"
        model.provider_type = Mock()
        model.provider_type.type_value = "litellm_proxy"
        return model

    @patch("rhesis.backend.app.utils.user_model_utils.get_model")
    @patch("rhesis.backend.app.utils.user_model_utils.crud.get_model")
    def test_fetch_and_configure_model_passes_endpoint(
        self, mock_get_model, mock_sdk_get_model, mock_db_model
    ):
        from sqlalchemy.orm import Session

        from rhesis.backend.app.utils.user_model_utils import _fetch_and_configure_model

        mock_db = Mock(spec=Session)
        mock_get_model.return_value = mock_db_model
        mock_sdk_get_model.return_value = Mock()

        _fetch_and_configure_model(
            db=mock_db,
            model_id="model-789",
            organization_id="org-456",
            default_model="gpt-4",
        )

        mock_sdk_get_model.assert_called_once_with(
            provider="litellm_proxy",
            model_name="gemini",
            api_key="test-key",
            model_type="language",
            api_base="http://host.docker.internal:4000",
        )

    @patch("rhesis.backend.app.utils.user_model_utils.get_model")
    @patch("rhesis.backend.app.utils.user_model_utils.crud.get_model")
    def test_fetch_and_configure_embedder_passes_endpoint(
        self, mock_get_model, mock_sdk_get_model, mock_db_model
    ):
        from sqlalchemy.orm import Session

        from rhesis.backend.app.utils.user_model_utils import _fetch_and_configure_embedder

        mock_db = Mock(spec=Session)
        mock_get_model.return_value = mock_db_model
        mock_sdk_get_model.return_value = Mock()

        _fetch_and_configure_embedder(
            db=mock_db,
            model_id="model-789",
            organization_id="org-456",
            default_model="openai",
        )

        mock_sdk_get_model.assert_called_once_with(
            provider="litellm_proxy",
            model_name="gemini",
            api_key="test-key",
            model_type="embedding",
            api_base="http://host.docker.internal:4000",
        )

    @patch("rhesis.backend.app.utils.user_model_utils.get_model")
    @patch("rhesis.backend.app.utils.user_model_utils.crud.get_model")
    def test_fetch_and_configure_model_omits_empty_endpoint(
        self, mock_get_model, mock_sdk_get_model, mock_db_model
    ):
        from sqlalchemy.orm import Session

        from rhesis.backend.app.utils.user_model_utils import _fetch_and_configure_model

        mock_db_model.endpoint = None
        mock_db = Mock(spec=Session)
        mock_get_model.return_value = mock_db_model
        mock_sdk_get_model.return_value = Mock()

        _fetch_and_configure_model(
            db=mock_db,
            model_id="model-789",
            organization_id="org-456",
            default_model="gpt-4",
        )

        mock_sdk_get_model.assert_called_once_with(
            provider="litellm_proxy",
            model_name="gemini",
            api_key="test-key",
            model_type="language",
        )
