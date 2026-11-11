"""
🔒 Token Management Security Tests

This module tests security vulnerabilities related to token management,
including token scoping, revocation, and organization-based access control.
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.crud import token as token_crud
from tests.backend.fixtures.rls import scope_to_org


@pytest.mark.security
class TestTokenOrganizationSecurity:
    """Test that token operations properly enforce organization-based security"""

    def test_revoke_user_tokens_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that revoke_user_tokens accepts organization filtering for token scoping"""
        import inspect

        # Verify that revoke_user_tokens accepts organization_id parameter (tokens may be organization-scoped)
        signature = inspect.signature(token_crud.revoke_user_tokens)
        assert "organization_id" in signature.parameters, (
            "revoke_user_tokens should accept organization_id for token scoping"
        )

        user_id = uuid.uuid4()
        org_id = str(uuid.uuid4())

        # Patch the bulk delete to check the organization filter reaches the WHERE clause.
        with patch.object(
            token_crud, "bulk_delete", side_effect=lambda _db, _model, criteria: criteria
        ):
            # Test with organization filtering
            with_org = token_crud.revoke_user_tokens(test_db, user_id, organization_id=org_id)
            assert with_org == 2

            # Test without organization filtering (should work but may revoke more tokens)
            without_org = token_crud.revoke_user_tokens(test_db, user_id)
            assert without_org == 1

    def test_get_token_by_value_organization_filtering(
        self, test_db: Session, test_organization, db_user
    ):
        """🔒 SECURITY: Test that get_token_by_value accepts organization filtering for token scoping"""
        import inspect

        # Verify that get_token_by_value accepts organization_id parameter (tokens may be organization-scoped)
        signature = inspect.signature(token_crud.get_token_by_value)
        assert "organization_id" in signature.parameters, (
            "get_token_by_value should accept organization_id for token scoping"
        )

        token_value = "test_token_value"
        org_id = str(uuid.uuid4())

        # Create a real token in the database instead of mocking
        from rhesis.backend.app.models.token import Token
        from rhesis.backend.app.utils.encryption import hash_token

        # Create a real token using existing fixtures
        token = Token(
            name="Test Token",
            token=token_value,
            token_hash=hash_token(token_value),
            token_obfuscated="test_***",
            token_type="api",
            user_id=db_user.id,
            organization_id=test_organization.id,
        )
        test_db.add(token)
        test_db.flush()

        # Test with organization filtering
        result_with_org = token_crud.get_token_by_value(
            test_db, token_value, organization_id=str(test_organization.id)
        )
        assert result_with_org is not None
        assert result_with_org.token == token_value
        assert result_with_org.organization_id == test_organization.id

        # Test without organization filtering (should still work)
        result_without_org = token_crud.get_token_by_value(test_db, token_value)
        assert result_without_org is not None
        assert result_without_org.token == token_value

    def test_create_token_organization_scoping(self, test_db: Session):
        """🔒 SECURITY: Test that create_token properly scopes tokens to organizations"""
        import inspect

        # Verify that create_token accepts organization_id parameter
        signature = inspect.signature(token_crud.create_token)
        assert "organization_id" in signature.parameters, (
            "create_token should accept organization_id for token scoping"
        )

        # Create a test organization and user
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org, user, _ = create_test_organization_and_user(
            test_db,
            f"Token Org {unique_id}",
            f"token-user-{unique_id}@security-test.com",
            "Token User",
        )
        org_id, user_id = org.id, user.id

        # Create a token with organization scoping
        import secrets

        from rhesis.backend.app.schemas.token import TokenCreate
        from rhesis.backend.app.utils.encryption import hash_token

        token_value = secrets.token_urlsafe(32)
        token_data = TokenCreate(
            name=f"Test Token {unique_id}",
            token=token_value,
            token_hash=hash_token(token_value),
            token_obfuscated=token_value[:8] + "...",
            user_id=user_id,
        )
        result = token_crud.create_token(
            test_db, token_data, organization_id=str(org_id), user_id=str(user_id)
        )

        # Verify the token was created with correct organization scoping
        assert result is not None
        assert str(result.user_id) == str(user_id)
        assert str(result.organization_id) == str(org_id)

    def test_revoke_token_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that revoke_token properly filters by organization"""
        import inspect

        # Verify that revoke_token accepts organization_id parameter
        signature = inspect.signature(token_crud.revoke_token)
        assert "organization_id" in signature.parameters, (
            "revoke_token should accept organization_id for token scoping"
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Token Delete Org 1 {unique_id}",
            f"token-delete-user1-{unique_id}@security-test.com",
            "Token Delete User 1",
        )
        org1_id, user1_id = org1.id, user1.id
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Token Delete Org 2 {unique_id}",
            f"token-delete-user2-{unique_id}@security-test.com",
            "Token Delete User 2",
        )
        org2_id, user2_id = org2.id, user2.id
        # The second org moved the session scope; rows below belong to
        # the first org, so scope back before inserting them.
        scope_to_org(test_db, org1_id)

        # Create a token in org1
        import secrets

        from rhesis.backend.app.schemas.token import TokenCreate
        from rhesis.backend.app.utils.encryption import hash_token

        token_value1 = secrets.token_urlsafe(32)
        token_data = TokenCreate(
            name=f"Test Token 1 {unique_id}",
            token=token_value1,
            token_hash=hash_token(token_value1),
            token_obfuscated=token_value1[:8] + "...",
            user_id=user1_id,
        )
        token = token_crud.create_token(
            test_db, token_data, organization_id=str(org1_id), user_id=str(user1_id)
        )

        # User from org1 should be able to revoke the token
        result_org1 = token_crud.revoke_token(
            test_db, token.id, organization_id=str(org1_id), user_id=str(user1_id)
        )
        assert result_org1 is not None  # Token was found and revoked

        # Create another token in org1 for the next test
        token_value2 = secrets.token_urlsafe(32)
        token_data2 = TokenCreate(
            name=f"Test Token 2 {unique_id}",
            token=token_value2,
            token_hash=hash_token(token_value2),
            token_obfuscated=token_value2[:8] + "...",
            user_id=user1_id,
        )
        token2 = token_crud.create_token(
            test_db, token_data2, organization_id=str(org1_id), user_id=str(user1_id)
        )

        # User from org2 should NOT be able to revoke the token from org1
        result_org2 = token_crud.revoke_token(
            test_db, token2.id, organization_id=str(org2_id), user_id=str(user2_id)
        )
        assert result_org2 is None  # Token was not found/revoked due to organization filtering


@pytest.mark.security
class TestTokenParameterValidation:
    """Test that token functions properly accept organization_id parameters for security"""

    def test_token_functions_accept_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Ensure all token-related functions accept organization filtering"""
        import inspect

        # List of token-related CRUD functions that should accept organization_id
        token_functions = [
            "revoke_user_tokens",
            "get_token_by_value",
            "create_token",
            "revoke_token",
        ]

        for func_name in token_functions:
            if hasattr(token_crud, func_name):
                func = getattr(token_crud, func_name)
                signature = inspect.signature(func)
                assert "organization_id" in signature.parameters, (
                    f"{func_name} should accept organization_id parameter"
                )

    def test_token_cross_tenant_isolation(self, test_db: Session):
        """🔒 SECURITY: Test that tokens are properly isolated between organizations"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        token_value = "test_token_123"

        with patch.object(test_db, "query") as mock_query:
            # Mock token from org1
            mock_token_org1 = Mock()
            mock_token_org1.token = token_value
            mock_token_org1.organization_id = uuid.UUID(org1_id)

            # Mock token from org2
            mock_token_org2 = Mock()
            mock_token_org2.token = token_value
            mock_token_org2.organization_id = uuid.UUID(org2_id)

            # When querying with org1 filter, should only return org1 token
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = (
                mock_token_org1
            )
            result_org1 = token_crud.get_token_by_value(
                test_db, token_value, organization_id=org1_id
            )
            assert result_org1.organization_id == uuid.UUID(org1_id)

            # When querying with org2 filter, should only return org2 token
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = (
                mock_token_org2
            )
            result_org2 = token_crud.get_token_by_value(
                test_db, token_value, organization_id=org2_id
            )
            assert result_org2.organization_id == uuid.UUID(org2_id)


@pytest.fixture
def colleague_token(test_db, test_org_id):
    """A token owned by another member of the caller's org."""
    from tests.backend.fixtures.test_setup import create_test_api_token, create_test_user

    suffix = uuid.uuid4().hex[:8]
    colleague = create_test_user(test_db, test_org_id, f"colleague-{suffix}@security-test.com")
    return create_test_api_token(test_db, colleague, name="Colleague token")


def _token_row(test_db, token_id):
    from rhesis.backend.app.models.token import Token

    test_db.expire_all()
    return test_db.query(Token).filter(Token.id == token_id).first()


@pytest.mark.security
class TestTokenOwnerScoping:
    """By-id token routes act only on the caller's own tokens, not a colleague's."""

    def test_read_colleague_token_is_404(self, authenticated_client, colleague_token):
        response = authenticated_client.get(f"/tokens/{colleague_token.id}")

        assert response.status_code == 404

    def test_update_colleague_token_is_404(self, authenticated_client, test_db, colleague_token):
        response = authenticated_client.put(
            f"/tokens/{colleague_token.id}", json={"name": "renamed"}
        )

        assert response.status_code == 404
        assert _token_row(test_db, colleague_token.id).name == "Colleague token"

    def test_refresh_colleague_token_is_404(self, authenticated_client, test_db, colleague_token):
        owner_id = colleague_token.user_id
        token_hash = colleague_token.token_hash

        response = authenticated_client.post(f"/tokens/{colleague_token.id}/refresh", json={})

        assert response.status_code == 404
        row = _token_row(test_db, colleague_token.id)
        assert row.user_id == owner_id
        assert row.token_hash == token_hash

    def test_delete_colleague_token_is_404(self, authenticated_client, test_db, colleague_token):
        response = authenticated_client.delete(f"/tokens/{colleague_token.id}")

        assert response.status_code == 404
        assert _token_row(test_db, colleague_token.id).deleted_at is None

    def test_bulk_delete_skips_colleague_token(
        self, authenticated_client, test_db, colleague_token
    ):
        response = authenticated_client.request(
            "DELETE", "/tokens/bulk", json={"token_ids": [str(colleague_token.id)]}
        )

        assert response.status_code == 200
        assert response.json() == {
            "deleted_ids": [],
            "not_found_ids": [str(colleague_token.id)],
        }
        assert _token_row(test_db, colleague_token.id).deleted_at is None

    def test_update_rejects_scopes(self, authenticated_client, test_db, authenticated_user_id):
        from rhesis.backend.app.models.user import User
        from tests.backend.fixtures.test_setup import create_test_api_token

        own = create_test_api_token(test_db, test_db.get(User, uuid.UUID(authenticated_user_id)))

        response = authenticated_client.put(f"/tokens/{own.id}", json={"scopes": ["x:read"]})

        assert response.status_code == 422
        assert _token_row(test_db, own.id).scopes is None

    def test_update_ignores_secret_fields(
        self, authenticated_client, test_db, authenticated_user_id
    ):
        from rhesis.backend.app.models.user import User
        from tests.backend.fixtures.test_setup import create_test_api_token

        own = create_test_api_token(test_db, test_db.get(User, uuid.UUID(authenticated_user_id)))
        token_hash = own.token_hash

        response = authenticated_client.put(
            f"/tokens/{own.id}",
            json={"name": "mine", "token_hash": "x" * 64, "token_type": "other"},
        )

        assert response.status_code == 200, response.text
        row = _token_row(test_db, own.id)
        assert row.name == "mine"
        assert row.token_hash == token_hash
        assert row.token_type == "bearer"
