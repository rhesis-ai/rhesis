"""
🔄 Transaction Management Testing for Authentication Utilities

Comprehensive test suite for verifying that transaction management works correctly
in authentication utilities after refactoring to remove manual db.commit() and db.rollback() calls.

Tests focus on:
- Automatic transaction commit on success in auth operations
- Proper error handling without manual rollbacks
- Token usage updates

Functions tested from auth utilities:
- token_validation.py: update_token_usage

Run with: python -m pytest tests/backend/auth/test_transaction_management.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth import token_validation
from rhesis.backend.app.utils.encryption import hash_token


@pytest.mark.unit
@pytest.mark.auth
@pytest.mark.transaction
class TestAuthTransactionManagement:
    """🔄 Test automatic transaction management in auth utilities"""

    def test_auth_utils_update_token_usage_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that token_validation.update_token_usage commits automatically on success"""
        # Create a test token
        token_value = "test_token_123"
        test_token = models.Token(
            name="Test Token",
            token=token_value,
            token_hash=hash_token(token_value),
            token_obfuscated="test_...123",
            token_type="bearer",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        test_db.add(test_token)
        test_db.flush()

        # Store original timestamp
        original_timestamp = test_token.last_used_at

        # Update token usage
        token_validation.update_token_usage(test_db, test_token)

        # Verify token usage was updated and persisted
        assert test_token.last_used_at is not None
        if original_timestamp:
            assert test_token.last_used_at > original_timestamp

        # Verify it's actually updated in the database (committed)
        db_token = test_db.query(models.Token).filter(models.Token.id == test_token.id).first()
        assert db_token is not None
        assert db_token.last_used_at is not None
        assert db_token.last_used_at == test_token.last_used_at

    def test_auth_utils_update_token_usage_handles_exception_gracefully(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """
        Test that token_validation.update_token_usage handles exceptions
        gracefully without manual rollback
        """
        # Create a test token
        token_value = "test_token_456"
        test_token = models.Token(
            name="Test Token",
            token=token_value,
            token_hash=hash_token(token_value),
            token_obfuscated="test_...456",
            token_type="bearer",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        test_db.add(test_token)
        test_db.flush()

        # Test with a token that has invalid data to trigger an exception
        # Create a token with invalid organization_id to cause an error
        invalid_token_value = "invalid_token"
        invalid_token = models.Token(
            name="Invalid Token",
            token=invalid_token_value,
            token_hash=hash_token(invalid_token_value),
            token_obfuscated="invalid_...",
            token_type="bearer",
            organization_id=uuid.uuid4(),  # Non-existent organization
            user_id=uuid.uuid4(),
        )

        # This should not raise an exception (error is caught and logged)
        token_validation.update_token_usage(test_db, invalid_token)

        # Verify the original token still exists and is not corrupted
        db_token = test_db.query(models.Token).filter(models.Token.id == test_token.id).first()
        assert db_token is not None
        assert db_token.token == "test_token_456"

    def test_token_validation_update_token_usage_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that token_validation.update_token_usage commits automatically on success"""
        # Create a test token
        token_value = "validation_token_123"
        test_token = models.Token(
            name="Validation Test Token",
            token=token_value,
            token_hash=hash_token(token_value),
            token_obfuscated="validation_...123",
            token_type="bearer",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        test_db.add(test_token)
        test_db.flush()

        # Store original timestamp
        original_timestamp = test_token.last_used_at

        # Update token usage
        token_validation.update_token_usage(test_db, test_token)

        # Verify token usage was updated and persisted
        assert test_token.last_used_at is not None
        if original_timestamp:
            assert test_token.last_used_at > original_timestamp

        # Verify it's actually updated in the database (committed)
        db_token = test_db.query(models.Token).filter(models.Token.id == test_token.id).first()
        assert db_token is not None
        assert db_token.last_used_at is not None
        assert db_token.last_used_at == test_token.last_used_at

    def test_token_validation_update_token_usage_handles_exception_gracefully(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """
        Test that token_validation.update_token_usage handles exceptions
        gracefully without manual rollback
        """
        # Create a test token
        token_value = "validation_token_456"
        test_token = models.Token(
            name="Validation Test Token",
            token=token_value,
            token_hash=hash_token(token_value),
            token_obfuscated="validation_...456",
            token_type="bearer",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        test_db.add(test_token)
        test_db.flush()

        # Test with a token that has invalid data to trigger an exception
        # Create a token with invalid organization_id to cause an error
        invalid_token_value = "invalid_token"
        invalid_token = models.Token(
            name="Invalid Token",
            token=invalid_token_value,
            token_hash=hash_token(invalid_token_value),
            token_obfuscated="invalid_...",
            token_type="bearer",
            organization_id=uuid.uuid4(),  # Non-existent organization
            user_id=uuid.UUID(authenticated_user_id),
        )

        # This should not raise an exception (error is caught and logged)
        token_validation.update_token_usage(test_db, invalid_token)

        # Verify the original token still exists and is not corrupted
        db_token = test_db.query(models.Token).filter(models.Token.id == test_token.id).first()
        assert db_token is not None
        assert db_token.token == "validation_token_456"

    def test_multiple_token_updates_transaction_isolation(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that multiple token updates maintain proper transaction isolation"""
        # Create multiple test tokens
        token1_value = "test_token_1"
        token1 = models.Token(
            name="Test Token 1",
            token=token1_value,
            token_hash=hash_token(token1_value),
            token_obfuscated="test_...1",
            token_type="bearer",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        token2_value = "test_token_2"
        token2 = models.Token(
            name="Test Token 2",
            token=token2_value,
            token_hash=hash_token(token2_value),
            token_obfuscated="test_...2",
            token_type="bearer",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )
        test_db.add_all([token1, token2])
        test_db.flush()

        # Store original timestamps
        original_timestamp1 = token1.last_used_at
        original_timestamp2 = token2.last_used_at

        # Update both tokens
        token_validation.update_token_usage(test_db, token1)
        token_validation.update_token_usage(test_db, token2)

        # Verify both tokens were updated independently
        assert token1.last_used_at is not None
        assert token2.last_used_at is not None

        if original_timestamp1:
            assert token1.last_used_at > original_timestamp1
        if original_timestamp2:
            assert token2.last_used_at > original_timestamp2

        # Verify both are persisted in database
        db_token1 = test_db.query(models.Token).filter(models.Token.id == token1.id).first()
        db_token2 = test_db.query(models.Token).filter(models.Token.id == token2.id).first()

        assert db_token1 is not None
        assert db_token2 is not None
        assert db_token1.last_used_at is not None
        assert db_token2.last_used_at is not None

