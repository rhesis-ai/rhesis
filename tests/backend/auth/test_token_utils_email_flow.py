"""
Unit tests for email-flow token functions (verification, password reset, magic link).
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from jose import jwt

from rhesis.backend.app.auth.constants import ALGORITHM
from rhesis.backend.app.auth.token_utils import (
    create_email_verification_token,
    create_magic_link_token,
    create_password_reset_token,
    verify_email_flow_token,
)

SECRET = "test-secret-key-for-tests"


@pytest.mark.unit
class TestEmailFlowTokenCreation:
    """Tests for email flow token creation."""

    @patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
    def test_create_email_verification_token_has_type_and_exp(
        self, mock_secret
    ):
        """Verification token has type email_verification and exp."""
        token = create_email_verification_token(
            user_id="user-123", email="test@example.com"
        )
        payload = jwt.decode(
            token, SECRET, algorithms=[ALGORITHM], options={"verify_exp": False}
        )
        assert payload["type"] == "email_verification"
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" not in payload

    @patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
    def test_create_password_reset_token_has_jti(self, mock_secret):
        """Password reset token includes jti for single-use."""
        token = create_password_reset_token(
            user_id="user-456", email="user@example.com"
        )
        payload = jwt.decode(
            token, SECRET, algorithms=[ALGORITHM], options={"verify_exp": False}
        )
        assert payload["type"] == "password_reset"
        assert payload["sub"] == "user-456"
        assert payload["email"] == "user@example.com"
        assert "jti" in payload
        assert len(payload["jti"]) == 36  # UUID format

    @patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
    def test_create_magic_link_token_has_jti(self, mock_secret):
        """Magic link token includes jti for single-use."""
        token = create_magic_link_token(
            user_id="user-789", email="link@example.com"
        )
        payload = jwt.decode(
            token, SECRET, algorithms=[ALGORITHM], options={"verify_exp": False}
        )
        assert payload["type"] == "magic_link"
        assert payload["email"] == "link@example.com"
        assert "jti" in payload


@pytest.mark.unit
class TestVerifyEmailFlowToken:
    """Tests for verify_email_flow_token."""

    @patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
    def test_verify_email_verification_token_success(self, mock_secret):
        """Valid email_verification token decodes correctly."""
        token = create_email_verification_token(
            user_id="user-1", email="v@example.com"
        )
        payload = verify_email_flow_token(token, "email_verification")
        assert payload["sub"] == "user-1"
        assert payload["email"] == "v@example.com"
        assert payload["type"] == "email_verification"

    @patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
    def test_verify_wrong_type_raises(self, mock_secret):
        """Using a verification token for password_reset raises."""
        token = create_email_verification_token(
            user_id="user-1", email="v@example.com"
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_email_flow_token(token, "password_reset")
        assert exc_info.value.status_code == 400
        assert "Invalid token type" in exc_info.value.detail

    @patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
    def test_verify_invalid_token_raises(self, mock_secret):
        """Invalid or tampered token raises."""
        with pytest.raises(HTTPException) as exc_info:
            verify_email_flow_token("invalid.jwt.token", "email_verification")
        assert exc_info.value.status_code == 400
        assert "Invalid token" in exc_info.value.detail or "expired" in (
            exc_info.value.detail or ""
        ).lower()

    @patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
    def test_verify_password_reset_returns_jti(self, mock_secret):
        """Password reset token verification returns jti."""
        token = create_password_reset_token(
            user_id="user-1", email="u@example.com"
        )
        payload = verify_email_flow_token(token, "password_reset")
        assert "jti" in payload
        assert payload["email"] == "u@example.com"
