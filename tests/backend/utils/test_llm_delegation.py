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
        return user

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    def test_delegation_call(self, mock_polyphemus_class, test_user):
        """Test calling Polyphemus with delegation token."""
        from rhesis.backend.app.utils.llm_utils import _call_polyphemus_with_delegation

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
        from rhesis.backend.app.utils.llm_utils import _call_polyphemus_with_delegation

        test_url = "http://localhost:8000"
        with patch.dict(os.environ, {"POLYPHEMUS_URL": test_url}):
            _call_polyphemus_with_delegation(test_user, "default")

            call_kwargs = mock_polyphemus_class.call_args[1]
            assert call_kwargs["base_url"] == test_url

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    def test_delegation_default_url(self, mock_polyphemus_class, test_user):
        """Test delegation uses default URL when not set."""
        from rhesis.backend.app.utils.llm_utils import _call_polyphemus_with_delegation

        # Remove POLYPHEMUS_URL if it exists
        with patch.dict(os.environ, {}, clear=False):
            if "POLYPHEMUS_URL" in os.environ:
                del os.environ["POLYPHEMUS_URL"]

            _call_polyphemus_with_delegation(test_user, "default")

            call_kwargs = mock_polyphemus_class.call_args[1]
            assert call_kwargs["base_url"] == "https://polyphemus.rhesis.ai"

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    def test_delegation_with_kwargs(self, mock_polyphemus_class, test_user):
        """Test delegation passes additional kwargs to PolyphemusLLM."""
        from rhesis.backend.app.utils.llm_utils import _call_polyphemus_with_delegation

        custom_kwargs = {"temperature": 0.7, "max_tokens": 1000}

        _call_polyphemus_with_delegation(test_user, "default", **custom_kwargs)

        call_kwargs = mock_polyphemus_class.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 1000

    @patch("rhesis.sdk.models.providers.polyphemus.PolyphemusLLM")
    @patch("rhesis.backend.app.auth.token_utils.create_service_delegation_token")
    def test_delegation_token_creation(self, mock_create_token, mock_polyphemus_class, test_user):
        """Test that delegation token is created with correct parameters."""
        from rhesis.backend.app.utils.llm_utils import _call_polyphemus_with_delegation

        mock_token = "mock.jwt.token"
        mock_create_token.return_value = mock_token

        _call_polyphemus_with_delegation(test_user, "default")

        # Verify token creation was called correctly
        mock_create_token.assert_called_once_with(test_user, "polyphemus")

        # Verify the token was passed to PolyphemusLLM
        call_kwargs = mock_polyphemus_class.call_args[1]
        assert call_kwargs["api_key"] == mock_token
