"""
🔑 Token CRUD Operations Testing

Comprehensive test suite for token-related CRUD operations.
Tests focus on token management operations while ensuring proper tenant
isolation and data integrity.

Functions tested:
- revoke_user_tokens: Revoke all tokens for a user

Run with: python -m pytest tests/backend/crud/test_token_crud.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.utils.encryption import hash_token


@pytest.mark.unit
@pytest.mark.crud
class TestTokenOperations:
    """🔑 Test token operations"""

    def test_revoke_user_tokens_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful token revocation for user"""
        # Create a separate test user to avoid revoking session tokens
        # that other tests depend on
        test_user_id = uuid.uuid4()
        test_user = models.User(
            email=f"test-token-user-{test_user_id}@example.com",
            name="Test Token User",
            auth0_id=f"test-token-user-auth0-{test_user_id}",
            organization_id=uuid.UUID(test_org_id),
        )
        test_db.add(test_user)
        test_db.flush()
        user_uuid = test_user.id

        # Create test tokens with proper Token model fields
        token_1_value = "test_token_1_abc123"
        db_token_1 = models.Token(
            name="Test Token 1",
            token=token_1_value,
            token_hash=hash_token(token_1_value),
            token_obfuscated="test_...123",
            token_type="bearer",
            user_id=user_uuid,
            organization_id=uuid.UUID(test_org_id),
        )

        token_2_value = "test_token_2_def456"
        db_token_2 = models.Token(
            name="Test Token 2",
            token=token_2_value,
            token_hash=hash_token(token_2_value),
            token_obfuscated="test_...456",
            token_type="bearer",
            user_id=user_uuid,
            organization_id=uuid.UUID(test_org_id),
        )

        test_db.add_all([db_token_1, db_token_2])
        test_db.flush()

        # Count tokens before revocation
        tokens_before = (
            test_db.query(models.Token).filter(models.Token.user_id == user_uuid).count()
        )

        # Test token revocation
        result = crud.revoke_user_tokens(db=test_db, user_id=user_uuid)

        # Verify tokens were revoked (result is count of deleted tokens)
        assert result == tokens_before
        assert tokens_before >= 2  # At least our 2 test tokens

        # Verify target user's tokens are deleted
        remaining_tokens = (
            test_db.query(models.Token).filter(models.Token.user_id == user_uuid).all()
        )
        assert len(remaining_tokens) == 0

    def test_revoke_user_tokens_no_tokens(self, test_db: Session):
        """Test token revocation for user with no tokens"""
        user_id = uuid.uuid4()

        result = crud.revoke_user_tokens(db=test_db, user_id=user_id)

        # Should return 0 for no tokens revoked
        assert result == 0
