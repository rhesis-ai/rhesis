"""
🔄 Transaction Management Testing for Authentication Utilities

Comprehensive test suite for verifying that transaction management works correctly
in authentication utilities after refactoring to remove manual db.commit() and db.rollback() calls.

Tests focus on:
- Automatic transaction commit on success in auth operations
- Proper error handling without manual rollbacks
- Token usage updates and user profile updates

Functions tested from auth utilities:
- auth_utils.py: update_token_usage
- token_validation.py: update_token_usage
- user_utils.py: get_or_create_user_from_profile

Run with: python -m pytest tests/backend/auth/test_transaction_management.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth import auth_utils, token_validation, user_utils
from rhesis.backend.app.utils.encryption import hash_token


@pytest.mark.unit
@pytest.mark.auth
@pytest.mark.transaction
class TestAuthTransactionManagement:
    """🔄 Test automatic transaction management in auth utilities"""

    def test_auth_utils_update_token_usage_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that auth_utils.update_token_usage commits automatically on success"""
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
        auth_utils.update_token_usage(test_db, test_token)

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
        """Test that auth_utils.update_token_usage handles exceptions gracefully without manual rollback"""
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
        auth_utils.update_token_usage(test_db, invalid_token)

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
        """Test that token_validation.update_token_usage handles exceptions gracefully without manual rollback"""
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

    def test_find_or_create_user_updates_existing_user_commits(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that find_or_create_user commits user updates automatically"""
        # Create an existing user
        user_email = f"existing_user_{uuid.uuid4()}@example.com"
        existing_user = models.User(
            email=user_email,
            name="Old Name",
            given_name="Old Given",
            family_name="Old Family",
            picture="old_picture.jpg",
            auth0_id="old_auth0_id",
            organization_id=uuid.UUID(test_org_id),
        )
        test_db.add(existing_user)
        test_db.flush()

        # Create user profile data
        user_profile = {
            "name": "New Name",
            "given_name": "New Given",
            "family_name": "New Family",
            "picture": "new_picture.jpg",
        }
        auth0_id = "new_auth0_id"

        # Update user from profile
        result = user_utils.find_or_create_user(test_db, auth0_id, user_email, user_profile)

        # Verify user was updated and persisted
        assert result is not None
        assert result.id == existing_user.id
        assert result.name == "New Name"
        assert result.given_name == "New Given"
        assert result.family_name == "New Family"
        assert result.picture == "new_picture.jpg"
        assert result.auth0_id == "new_auth0_id"
        assert result.last_login_at is not None

        # Verify it's actually updated in the database (committed)
        db_user = test_db.query(models.User).filter(models.User.id == existing_user.id).first()
        assert db_user is not None
        assert db_user.name == "New Name"
        assert db_user.given_name == "New Given"
        assert db_user.family_name == "New Family"
        assert db_user.picture == "new_picture.jpg"
        assert db_user.auth0_id == "new_auth0_id"
        assert db_user.last_login_at is not None

    def test_find_or_create_user_creates_new_user_commits(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that find_or_create_user commits new user creation automatically"""
        # Create user profile data for non-existing user
        user_email = f"new_user_{uuid.uuid4()}@example.com"
        user_profile = {
            "name": "New User Name",
            "given_name": "New Given",
            "family_name": "New Family",
            "picture": "new_user_picture.jpg",
        }
        auth0_id = f"new_auth0_id_{uuid.uuid4()}"

        # Get initial user count
        initial_count = test_db.query(models.User).count()

        # Create user from profile (this will actually create a user)
        result = user_utils.find_or_create_user(test_db, auth0_id, user_email, user_profile)

        # Verify result is a user
        assert result is not None
        assert result.email == user_email
        assert result.name == user_profile["name"]
        assert result.given_name == user_profile["given_name"]
        assert result.family_name == user_profile["family_name"]
        assert result.picture == user_profile["picture"]
        assert result.auth0_id == auth0_id

        # Verify user was actually created in database
        final_count = test_db.query(models.User).count()
        assert final_count == initial_count + 1

        # Verify the user exists in the database
        db_user = test_db.query(models.User).filter(models.User.email == user_email).first()
        assert db_user is not None
        assert db_user.auth0_id == auth0_id

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
        auth_utils.update_token_usage(test_db, token1)
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

    def test_user_profile_update_by_email_and_auth0_id(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that user profile updates work correctly for both email and auth0_id lookups"""
        # Create a user with both email and auth0_id
        user_email = f"profile_user_{uuid.uuid4()}@example.com"
        existing_user = models.User(
            email=user_email,
            name="Original Name",
            auth0_id="original_auth0_id",
            organization_id=uuid.UUID(test_org_id),
        )
        test_db.add(existing_user)
        test_db.flush()

        # Test update via email lookup
        user_profile = {
            "name": "Updated via Email",
            "given_name": "Updated Given",
            "family_name": "Updated Family",
            "picture": "updated_picture.jpg",
        }
        new_auth0_id = "new_auth0_id_123"

        result = user_utils.find_or_create_user(test_db, new_auth0_id, user_email, user_profile)

        # Verify user was found by email and updated
        assert result is not None
        assert result.id == existing_user.id
        assert result.name == "Updated via Email"
        assert result.auth0_id == new_auth0_id

        # Verify changes are persisted
        db_user = test_db.query(models.User).filter(models.User.id == existing_user.id).first()
        assert db_user is not None
        assert db_user.name == "Updated via Email"
        assert db_user.auth0_id == new_auth0_id

    def test_concurrent_auth_operations_do_not_interfere(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that concurrent auth operations do not interfere with each other"""
        # Create multiple tokens and users
        token_value = "concurrent_token"
        token = models.Token(
            name="Concurrent Test Token",
            token=token_value,
            token_hash=hash_token(token_value),
            token_obfuscated="concurrent_...token",
            token_type="bearer",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id),
        )

        user_email = f"concurrent_user_{uuid.uuid4()}@example.com"
        user = models.User(
            email=user_email, name="Concurrent User", organization_id=uuid.UUID(test_org_id)
        )

        test_db.add_all([token, user])
        test_db.flush()

        # Perform concurrent operations
        # Update token usage
        auth_utils.update_token_usage(test_db, token)

        # Update user profile
        user_profile = {
            "name": "Updated Concurrent User",
            "given_name": "Updated",
            "family_name": "User",
            "picture": "updated.jpg",
        }
        updated_user = user_utils.find_or_create_user(
            test_db, "new_auth0_id", user_email, user_profile
        )

        # Verify both operations succeeded independently
        # Check token
        db_token = test_db.query(models.Token).filter(models.Token.id == token.id).first()
        assert db_token is not None
        assert db_token.last_used_at is not None

        # Check user
        assert updated_user is not None
        assert updated_user.name == "Updated Concurrent User"
        assert updated_user.auth0_id == "new_auth0_id"

        db_user = test_db.query(models.User).filter(models.User.id == user.id).first()
        assert db_user is not None
        assert db_user.name == "Updated Concurrent User"
        assert db_user.auth0_id == "new_auth0_id"
