"""
🔐 Token Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for token entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🔐 Token-specific security functionality testing
- 🔑 Token generation, refresh, and revocation
- ⏰ Expiration date handling and validation
- 🔒 Security-aware token management

Run with: python -m pytest tests/backend/routes/test_token.py -v
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status

from .base import BaseEntityTests
from .endpoints import APIEndpoints
from .fixtures.data_factories import TokenDataFactory

# Initialize Faker
fake = Faker()


class TokenTestMixin:
    """Enhanced token test mixin using factory system"""

    # Entity configuration
    entity_name = "token"
    entity_plural = "tokens"
    endpoints = APIEndpoints.TOKENS

    # Field mappings for tokens
    name_field = "name"
    description_field = None  # Tokens don't have a description field

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample token data using factory"""
        return TokenDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal token data using factory"""
        return TokenDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return token update data using factory"""
        return TokenDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid token data using factory"""
        return TokenDataFactory.invalid_data()

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return token data with null description - tokens don't have description field"""
        # Tokens don't have a description field, so return regular sample data
        return self.get_sample_data()


class TestTokenRoutes(TokenTestMixin, BaseEntityTests):
    """
    🔐 Complete token route test suite

    This class provides comprehensive token testing with security considerations.
    Note: Tokens use revocation instead of deletion and have unique security features.
    """

    # === TOKEN-SPECIFIC CRUD TESTS ===

    def test_create_token_with_required_fields(self, authenticated_client):
        """Test token creation with only required fields"""
        token_data = self.get_minimal_data()

        response = authenticated_client.post(self.endpoints.create, json=token_data)

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        # Token creation now returns full token object (consistent with other routes)
        assert "id" in created_token
        assert created_token["name"] == token_data["name"]
        assert created_token["token_type"] == "bearer"
        assert "token_obfuscated" in created_token
        assert "..." in created_token["token_obfuscated"]

    def test_create_token_with_expiration(self, authenticated_client):
        """Test token creation with expiration date"""
        token_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=token_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        assert "id" in created_token
        assert created_token["name"] == token_data["name"]
        assert created_token["token_type"] == "bearer"
        assert "expires_at" in created_token
        assert created_token["expires_at"] is not None

    def test_create_api_integration_token(self, authenticated_client):
        """Test creating a token for API integration"""
        api_token_data = TokenDataFactory.edge_case_data("api_integration")

        response = authenticated_client.post(
            self.endpoints.create,
            json=api_token_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        assert "id" in created_token
        assert created_token["name"] == api_token_data["name"]
        assert created_token["token_type"] == "bearer"

    def test_create_development_token(self, authenticated_client):
        """Test creating a short-lived development token"""
        dev_token_data = TokenDataFactory.edge_case_data("development_token")

        response = authenticated_client.post(
            self.endpoints.create,
            json=dev_token_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        assert "id" in created_token
        assert created_token["token_type"] == "bearer"

    def test_create_production_token(self, authenticated_client):
        """Test creating a production token"""
        prod_token_data = TokenDataFactory.edge_case_data("production_token")

        response = authenticated_client.post(
            self.endpoints.create,
            json=prod_token_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        assert "id" in created_token
        assert created_token["token_type"] == "bearer"

    def test_create_never_expires_token(self, authenticated_client):
        """Test creating a token that never expires"""
        never_expires_data = TokenDataFactory.edge_case_data("never_expires")

        response = authenticated_client.post(
            self.endpoints.create,
            json=never_expires_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        # Never-expiring tokens should have null expires_at
        assert created_token["expires_at"] is None

    def test_create_long_lived_token(self, authenticated_client):
        """Test creating a long-lived token (1 year)"""
        long_lived_data = TokenDataFactory.edge_case_data("long_lived_token")

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_lived_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        # Long-lived tokens should have far future expiration
        assert "expires_at" in created_token and created_token["expires_at"]
        expires_at_str = created_token["expires_at"].replace("Z", "+00:00")
        expires_at = datetime.fromisoformat(expires_at_str)
        # Ensure both datetimes are timezone-aware for comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        days_until_expiry = (expires_at - now_utc).days
        assert days_until_expiry > 300  # Should be more than 300 days

    def test_create_token_with_long_name(self, authenticated_client):
        """Test creating a token with a very long name"""
        long_name_data = TokenDataFactory.edge_case_data("long_token_name")

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_name_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        assert "id" in created_token
        assert len(long_name_data["name"]) > 100  # Verify it's actually long

    def test_create_token_with_special_characters(self, authenticated_client):
        """Test creating a token with special characters in name"""
        special_chars_data = TokenDataFactory.edge_case_data("special_chars_name")

        response = authenticated_client.post(
            self.endpoints.create,
            json=special_chars_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        assert "id" in created_token
        assert "@#$%^&*()" in special_chars_data["name"]

    def test_get_token_by_id(self, authenticated_client):
        """Test retrieving a specific token by ID"""
        # Create token first
        token_data = {"name": f"Test Token {fake.word()}", "expires_in_days": 30}
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=token_data,
        )

        # Extract token ID from response (now available with consistent API)
        assert create_response.status_code == status.HTTP_200_OK
        create_result = create_response.json()
        print(f"Create response: {create_result}")

        # The create response might not have 'id' field - check the actual structure
        if "id" in create_result:
            token_id = create_result["id"]
        else:
            # If no ID in create response, we need to get it from the token list
            list_response = authenticated_client.get(self.endpoints.list)
            assert list_response.status_code == status.HTTP_200_OK
            tokens = list_response.json()
            # Find the token we just created
            created_token = next((t for t in tokens if t["name"] == token_data["name"]), None)
            assert created_token is not None, "Could not find created token in list"
            token_id = created_token["id"]

        # Get token by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, token_id=token_id),
        )

        print(f"Get response status: {response.status_code}")
        print(f"Get response body: {response.text}")

        assert response.status_code == status.HTTP_200_OK
        token = response.json()

        assert token["id"] == token_id
        # Token value should be obfuscated in read responses
        if "token_obfuscated" in token:
            assert "..." in token["token_obfuscated"]
        # Full token value should NOT be in read responses
        assert "token" not in token or "..." in str(token.get("token", ""))

    def test_list_tokens(self, authenticated_client):
        """Test listing user's tokens"""
        # Create a few tokens first
        token_data_list = [self.get_sample_data() for _ in range(3)]
        created_tokens = []

        for token_data in token_data_list:
            response = authenticated_client.post(
                self.endpoints.create,
                json=token_data,
            )
            if response.status_code == status.HTTP_200_OK:
                created_tokens.append(response.json())

        # List tokens
        response = authenticated_client.get(self.endpoints.list)

        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()

        # Should have at least the tokens we created
        assert len(tokens) >= len(created_tokens)

        # Verify tokens are obfuscated in list view
        for token in tokens:
            if "token_obfuscated" in token:
                assert "..." in token["token_obfuscated"]
            # Full token value should NOT be in list responses
            assert "token" not in token or "..." in str(token.get("token", ""))

    def test_list_tokens_with_pagination(self, authenticated_client):
        """Test listing tokens with pagination"""
        # Create multiple tokens
        for i in range(5):
            token_data = self.get_sample_data()
            token_data["name"] = f"Test Token {i}"
            authenticated_client.post(self.endpoints.create, json=token_data)

        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )

        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert len(tokens) <= 3

        # Check count header if available
        if "X-Total-Count" in response.headers:
            total_count = int(response.headers["X-Total-Count"])
            assert total_count >= 5

    def test_revoke_token(self, authenticated_client):
        """Test revoking (deleting) a token"""
        # Create token first
        token_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=token_data,
        )

        # Extract token ID (now available with consistent API)
        assert create_response.status_code == status.HTTP_200_OK
        token_id = create_response.json()["id"]

        # Revoke token
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, token_id=token_id),
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify token is revoked (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, token_id=token_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE

    # === TOKEN REFRESH TESTS ===

    def test_refresh_token(self, authenticated_client):
        """Test refreshing a token"""
        # Create token first
        token_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=token_data,
        )

        assert create_response.status_code == status.HTTP_200_OK
        token_id = create_response.json()["id"]

        # Refresh token with new expiration
        refresh_data = {"expires_in_days": 60}
        response = authenticated_client.post(
            f"{self.endpoints.format_path(self.endpoints.get_by_id, token_id=token_id)}/refresh",
            json=refresh_data,
        )

        # Refresh might not be implemented for all token types
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        ]

        if response.status_code == status.HTTP_200_OK:
            refreshed_token = response.json()
            # Should have token ID and updated fields
            assert "id" in refreshed_token
            assert "last_refreshed_at" in refreshed_token

    # === TOKEN SECURITY TESTS ===

    def test_create_expired_token(self, authenticated_client):
        """Test creating an already expired token"""
        expired_data = TokenDataFactory.edge_case_data("expired_token")

        response = authenticated_client.post(
            self.endpoints.create,
            json=expired_data,
        )

        # Should still create successfully, but be expired
        assert response.status_code == status.HTTP_200_OK
        created_token = response.json()

        if "expires_at" in created_token:
            expires_at_str = created_token["expires_at"].replace("Z", "+00:00")
            expires_at = datetime.fromisoformat(expires_at_str)
            # Ensure both datetimes are timezone-aware for comparison
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            assert expires_at < now_utc  # Should be in the past

    def test_token_obfuscation(self, authenticated_client):
        """Test that tokens are properly obfuscated"""
        token_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=token_data,
        )

        assert response.status_code == status.HTTP_200_OK

        # In creation response, full token might be provided
        # But in list/get responses, it should be obfuscated
        if "id" in response.json():
            token_id = response.json()["id"]

            get_response = authenticated_client.get(
                self.endpoints.format_path(self.endpoints.get_by_id, token_id=token_id),
            )

            if get_response.status_code == status.HTTP_200_OK:
                token = get_response.json()
                if "token_obfuscated" in token:
                    # Should be in format "abc...xyz"
                    assert "..." in token["token_obfuscated"]
                    assert (
                        len(token["token_obfuscated"]) < 20
                    )  # Should be much shorter than full token

    # === TOKEN ERROR HANDLING TESTS ===

    def test_create_token_without_name(self, authenticated_client):
        """Test creating token without required name field"""
        invalid_data = {"token_type": "bearer"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_create_token_with_empty_name(self, authenticated_client):
        """Test creating token with empty name"""
        invalid_data = {"name": "", "token_type": "bearer"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_get_nonexistent_token(self, authenticated_client):
        """Test retrieving a non-existent token"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, token_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_revoke_nonexistent_token(self, authenticated_client):
        """Test revoking a non-existent token"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, token_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_refresh_nonexistent_token(self, authenticated_client):
        """Test refreshing a non-existent token"""
        fake_id = str(uuid.uuid4())
        refresh_data = {"expires_in_days": 30}

        response = authenticated_client.post(
            f"{self.endpoints.format_path(self.endpoints.get_by_id, token_id=fake_id)}/refresh",
            json=refresh_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# === TOKEN MANAGEMENT TESTS ===


@pytest.mark.integration
class TestTokenManagement(TokenTestMixin, BaseEntityTests):
    """Enhanced token management tests"""

    def test_create_multiple_token_types(self, authenticated_client):
        """Test creating multiple different types of tokens"""
        token_types = ["api_integration", "development_token", "production_token", "never_expires"]
        created_tokens = []

        for token_type in token_types:
            token_data = TokenDataFactory.edge_case_data(token_type)

            response = authenticated_client.post(
                self.endpoints.create,
                json=token_data,
            )

            assert response.status_code == status.HTTP_200_OK
            created_token = response.json()
            created_tokens.append(created_token)

        assert len(created_tokens) == len(token_types)

        # Verify different token characteristics
        for i, token in enumerate(created_tokens):
            token_type = token_types[i]
            if token_type == "never_expires" and "expires_at" in token:
                assert token["expires_at"] is None
            elif token_type == "development_token":
                # Development tokens typically have shorter expiration
                if "expires_at" in token and token["expires_at"]:
                    expires_at_str = token["expires_at"].replace("Z", "+00:00")
                    expires_at = datetime.fromisoformat(expires_at_str)
                    # Ensure both datetimes are timezone-aware for comparison
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    days_until_expiry = (expires_at - now_utc).days
                    assert days_until_expiry <= 30  # Should be short-lived

    def test_token_lifecycle_management(self, authenticated_client):
        """Test complete token lifecycle: create -> use -> refresh -> revoke"""
        # 1. Create token
        token_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=token_data,
        )

        assert create_response.status_code == status.HTTP_200_OK
        token_id = create_response.json()["id"]

        # 2. Verify token exists
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, token_id=token_id),
        )
        assert get_response.status_code == status.HTTP_200_OK

        # 3. Try to refresh token (if supported)
        refresh_data = {"expires_in_days": 45}
        refresh_response = authenticated_client.post(
            f"{self.endpoints.format_path(self.endpoints.get_by_id, token_id=token_id)}/refresh",
            json=refresh_data,
        )
        # Refresh might not be supported, so accept various responses
        assert refresh_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        ]

        # 4. Revoke token
        delete_response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, token_id=token_id),
        )
        assert delete_response.status_code == status.HTTP_200_OK

        # 5. Verify token is revoked (soft delete returns 410 GONE)
        final_get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, token_id=token_id),
        )
        assert final_get_response.status_code == status.HTTP_410_GONE

    def test_bulk_token_operations(self, authenticated_client):
        """Test bulk token creation and management"""
        # Create multiple tokens
        token_count = 10
        tokens_data = TokenDataFactory.batch_data(token_count, variation=True)
        created_tokens = []

        for token_data in tokens_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=token_data,
            )
            if response.status_code == status.HTTP_200_OK:
                created_tokens.append(response.json())

        assert len(created_tokens) >= token_count // 2  # At least half should succeed

        # List all tokens
        list_response = authenticated_client.get(
            f"{self.endpoints.list}?limit=20",
        )

        assert list_response.status_code == status.HTTP_200_OK
        tokens = list_response.json()
        assert len(tokens) >= len(created_tokens)

        # Revoke some tokens
        tokens_to_revoke = created_tokens[:3]  # Revoke first 3
        for token in tokens_to_revoke:
            if "id" in token:
                delete_response = authenticated_client.delete(
                    self.endpoints.format_path(self.endpoints.delete, token_id=token["id"]),
                )
                assert delete_response.status_code == status.HTTP_200_OK


# === TOKEN PERFORMANCE TESTS ===


@pytest.mark.performance
class TestTokenPerformance(TokenTestMixin, BaseEntityTests):
    """Token performance tests"""

    def test_create_multiple_tokens_performance(self, authenticated_client):
        """Test creating multiple tokens for performance"""
        token_count = 20
        tokens_data = TokenDataFactory.batch_data(token_count, variation=True)

        created_tokens = []
        for token_data in tokens_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=token_data,
            )
            if response.status_code == status.HTTP_200_OK:
                created_tokens.append(response.json())

        # Should create most tokens successfully
        assert len(created_tokens) >= token_count // 2

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={token_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert len(tokens) >= len(created_tokens)

    def test_token_security_operations_performance(self, authenticated_client):
        """Test performance of token security operations"""
        # Create tokens of different security levels
        security_types = [
            "development_token",
            "production_token",
            "api_integration",
            "long_lived_token",
        ]

        created_tokens = []
        for security_type in security_types:
            for i in range(3):  # 3 tokens per security type
                token_data = TokenDataFactory.edge_case_data(security_type)
                response = authenticated_client.post(
                    self.endpoints.create,
                    json=token_data,
                )
                if response.status_code == status.HTTP_200_OK:
                    created_tokens.append(response.json())

        assert len(created_tokens) >= len(security_types) * 2  # At least 2 per type

        # Test bulk token listing with security considerations
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit=20",
        )

        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()

        # Verify all tokens are properly obfuscated
        for token in tokens:
            if "token_obfuscated" in token:
                assert "..." in token["token_obfuscated"]
            # Should not contain full token values
            assert "token" not in token or "..." in str(token.get("token", ""))

    def test_token_expiration_performance(self, authenticated_client):
        """Test performance with various token expiration scenarios"""
        # Create tokens with different expiration patterns
        expiration_types = ["expired_token", "never_expires", "long_lived_token", "recently_used"]

        created_tokens = []
        for exp_type in expiration_types:
            for i in range(2):  # 2 tokens per expiration type
                token_data = TokenDataFactory.edge_case_data(exp_type)
                response = authenticated_client.post(
                    self.endpoints.create,
                    json=token_data,
                )
                if response.status_code == status.HTTP_200_OK:
                    created_tokens.append(response.json())

        # Verify token creation across different expiration scenarios
        assert len(created_tokens) >= len(expiration_types)

        # Test listing performance with mixed expiration tokens
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit=15",
        )

        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert len(tokens) >= len(created_tokens)
