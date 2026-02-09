"""
Refresh Token Utilities Test Suite

Unit tests for refresh_token_utils.py covering:
- Token creation and hashing
- Expired token rejection
- Reuse detection (family revocation)
- revoke_all_for_user
- cleanup_expired_tokens
- Token model properties (is_expired, is_revoked, is_valid)

Run with: python -m pytest tests/backend/auth/test_refresh_token_utils.py -v
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from rhesis.backend.app.auth.refresh_token_utils import (
    _hash_token,
    cleanup_expired_tokens,
    create_refresh_token,
    revoke_all_for_user,
    verify_and_rotate_refresh_token,
)
from rhesis.backend.app.models.refresh_token import RefreshToken
from tests.backend.fixtures.test_setup import (
    create_test_organization,
    create_test_user,
)


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.rhesis.ai"


# =============================================================================
# Token creation
# =============================================================================


@pytest.mark.unit
class TestCreateRefreshToken:
    """Tests for create_refresh_token."""

    def test_returns_non_empty_string(self, test_db):
        org = create_test_organization(test_db, "Create Org")
        user = create_test_user(
            test_db, org.id, _unique_email("create"), "Create User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        assert isinstance(raw, str)
        assert len(raw) > 0

    def test_persists_hashed_token_in_db(self, test_db):
        org = create_test_organization(test_db, "Persist Org")
        user = create_test_user(
            test_db, org.id, _unique_email("persist"), "Persist User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        expected_hash = _hash_token(raw)
        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == expected_hash)
            .first()
        )
        assert row is not None
        assert str(row.user_id) == str(user.id)

    def test_assigns_new_family_when_none(self, test_db):
        org = create_test_organization(test_db, "Family Org")
        user = create_test_user(
            test_db, org.id, _unique_email("family"), "Family User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        assert row.family_id is not None

    def test_uses_provided_family_id(self, test_db):
        org = create_test_organization(test_db, "FamID Org")
        user = create_test_user(
            test_db, org.id, _unique_email("famid"), "FamID User"
        )
        test_db.flush()

        family = str(uuid.uuid4())
        raw = create_refresh_token(
            test_db, str(user.id), family_id=family
        )
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        assert str(row.family_id) == family

    def test_each_call_produces_unique_token(self, test_db):
        org = create_test_organization(test_db, "Unique Org")
        user = create_test_user(
            test_db, org.id, _unique_email("unique"), "Unique User"
        )
        test_db.flush()

        raw1 = create_refresh_token(test_db, str(user.id))
        raw2 = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        assert raw1 != raw2


# =============================================================================
# Verify and rotate
# =============================================================================


@pytest.mark.unit
class TestVerifyAndRotate:
    """Tests for verify_and_rotate_refresh_token."""

    def test_valid_token_rotates(self, test_db):
        """A fresh token should be accepted, revoked, and a new one issued."""
        org = create_test_organization(test_db, "Rotate Org")
        user = create_test_user(
            test_db, org.id, _unique_email("rotate"), "Rotate User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        old_token, new_raw = verify_and_rotate_refresh_token(test_db, raw)
        test_db.commit()

        assert old_token.is_revoked
        assert new_raw != raw
        assert isinstance(new_raw, str)

    def test_expired_token_rejected(self, test_db):
        """A token whose expires_at is in the past should be rejected."""
        org = create_test_organization(test_db, "Expired Org")
        user = create_test_user(
            test_db, org.id, _unique_email("expired"), "Expired User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        # Manually back-date the expiry
        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        test_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            verify_and_rotate_refresh_token(test_db, raw)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_unknown_token_rejected(self, test_db):
        """A token that was never issued should be rejected."""
        with pytest.raises(HTTPException) as exc_info:
            verify_and_rotate_refresh_token(test_db, "never-issued-token")

        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()

    def test_reuse_revokes_entire_family(self, test_db):
        """Presenting a rotated (revoked) token should revoke its family."""
        org = create_test_organization(test_db, "Reuse Org")
        user = create_test_user(
            test_db, org.id, _unique_email("reuse"), "Reuse User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        # First rotation succeeds and returns a new token
        _, new_raw = verify_and_rotate_refresh_token(test_db, raw)
        test_db.commit()

        # Reuse of the old token triggers family revocation
        with pytest.raises(HTTPException) as exc_info:
            verify_and_rotate_refresh_token(test_db, raw)

        assert exc_info.value.status_code == 401
        assert "reuse" in exc_info.value.detail.lower()

        # The new token (which was valid) should now also be revoked
        with pytest.raises(HTTPException) as exc_info:
            verify_and_rotate_refresh_token(test_db, new_raw)

        assert exc_info.value.status_code == 401

    def test_rotation_preserves_family_id(self, test_db):
        """Rotated tokens should stay in the same family."""
        org = create_test_organization(test_db, "PresFam Org")
        user = create_test_user(
            test_db, org.id, _unique_email("presfam"), "PresFam User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        old_row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        original_family = str(old_row.family_id)

        _, new_raw = verify_and_rotate_refresh_token(test_db, raw)
        test_db.commit()

        new_row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(new_raw))
            .first()
        )
        assert str(new_row.family_id) == original_family


# =============================================================================
# Revoke all for user
# =============================================================================


@pytest.mark.unit
class TestRevokeAllForUser:
    """Tests for revoke_all_for_user."""

    def test_revokes_all_active_tokens(self, test_db):
        org = create_test_organization(test_db, "RevokeAll Org")
        user = create_test_user(
            test_db, org.id, _unique_email("revokeall"), "RevokeAll User"
        )
        test_db.flush()

        raw1 = create_refresh_token(test_db, str(user.id))
        raw2 = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        count = revoke_all_for_user(test_db, str(user.id))
        test_db.commit()

        assert count == 2

        # Both tokens should now be rejected
        with pytest.raises(HTTPException):
            verify_and_rotate_refresh_token(test_db, raw1)
        with pytest.raises(HTTPException):
            verify_and_rotate_refresh_token(test_db, raw2)

    def test_returns_zero_when_no_tokens(self, test_db):
        org = create_test_organization(test_db, "NoTok Org")
        user = create_test_user(
            test_db, org.id, _unique_email("notok"), "NoTok User"
        )
        test_db.flush()

        count = revoke_all_for_user(test_db, str(user.id))
        assert count == 0

    def test_does_not_affect_other_users(self, test_db):
        org = create_test_organization(test_db, "OtherUser Org")
        user_a = create_test_user(
            test_db, org.id, _unique_email("usera"), "User A"
        )
        user_b = create_test_user(
            test_db, org.id, _unique_email("userb"), "User B"
        )
        test_db.flush()

        create_refresh_token(test_db, str(user_a.id))
        raw_b = create_refresh_token(test_db, str(user_b.id))
        test_db.commit()

        revoke_all_for_user(test_db, str(user_a.id))
        test_db.commit()

        # User B's token should still work
        _, new_raw_b = verify_and_rotate_refresh_token(test_db, raw_b)
        test_db.commit()
        assert new_raw_b is not None


# =============================================================================
# Cleanup expired tokens
# =============================================================================


@pytest.mark.unit
class TestCleanupExpiredTokens:
    """Tests for cleanup_expired_tokens."""

    def test_deletes_old_expired_tokens(self, test_db):
        org = create_test_organization(test_db, "Cleanup Org")
        user = create_test_user(
            test_db, org.id, _unique_email("cleanup"), "Cleanup User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        # Back-date the token far past the retention window
        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=30)
        test_db.commit()

        count = cleanup_expired_tokens(test_db)
        test_db.commit()

        assert count >= 1

        # Verify the row is actually gone
        deleted = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        assert deleted is None

    def test_does_not_delete_fresh_tokens(self, test_db):
        org = create_test_organization(test_db, "Fresh Org")
        user = create_test_user(
            test_db, org.id, _unique_email("fresh"), "Fresh User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        cleanup_expired_tokens(test_db)
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        assert row is not None


# =============================================================================
# Model property tests
# =============================================================================


@pytest.mark.unit
class TestRefreshTokenModelProperties:
    """Tests for RefreshToken model computed properties."""

    def test_is_expired_false_for_future_expiry(self, test_db):
        org = create_test_organization(test_db, "PropFuture Org")
        user = create_test_user(
            test_db, org.id, _unique_email("propfut"), "PropFuture User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        assert row.is_expired is False

    def test_is_expired_true_for_past_expiry(self, test_db):
        org = create_test_organization(test_db, "PropPast Org")
        user = create_test_user(
            test_db, org.id, _unique_email("proppast"), "PropPast User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert row.is_expired is True

    def test_is_revoked_false_when_not_revoked(self, test_db):
        org = create_test_organization(test_db, "NotRevoked Org")
        user = create_test_user(
            test_db, org.id, _unique_email("notrev"), "NotRevoked User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        assert row.is_revoked is False

    def test_is_revoked_true_after_revocation(self, test_db):
        org = create_test_organization(test_db, "Revoked Org")
        user = create_test_user(
            test_db, org.id, _unique_email("revoked"), "Revoked User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        row.revoked_at = datetime.now(timezone.utc)
        assert row.is_revoked is True

    def test_is_valid_true_when_fresh_and_unrevoked(self, test_db):
        org = create_test_organization(test_db, "Valid Org")
        user = create_test_user(
            test_db, org.id, _unique_email("valid"), "Valid User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        assert row.is_valid is True

    def test_is_valid_false_when_expired(self, test_db):
        org = create_test_organization(test_db, "InvalidExp Org")
        user = create_test_user(
            test_db, org.id, _unique_email("invalexp"), "InvalidExp User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert row.is_valid is False

    def test_is_valid_false_when_revoked(self, test_db):
        org = create_test_organization(test_db, "InvalidRev Org")
        user = create_test_user(
            test_db, org.id, _unique_email("invalrev"), "InvalidRev User"
        )
        test_db.flush()

        raw = create_refresh_token(test_db, str(user.id))
        test_db.commit()

        row = (
            test_db.query(RefreshToken)
            .filter(RefreshToken.token_hash == _hash_token(raw))
            .first()
        )
        row.revoked_at = datetime.now(timezone.utc)
        assert row.is_valid is False
