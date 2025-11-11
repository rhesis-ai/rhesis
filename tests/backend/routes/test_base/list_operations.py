"""
List Operation Tests

This module provides comprehensive testing for list operations including
pagination, sorting, filtering, and user-based filtering.
"""

import uuid

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .core import BaseEntityTests

# Initialize Faker
fake = Faker()


@pytest.mark.integration
@pytest.mark.critical
class BaseListOperationTests(BaseEntityTests):
    """Base class for list operation tests"""

    def test_list_entities_empty(self, authenticated_client: TestClient):
        """Test listing entities when none exist"""
        response = authenticated_client.get(self.endpoints.list)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)

    def test_list_entities_with_data(self, authenticated_client: TestClient):
        """Test listing entities with existing data"""
        created_entity = self.create_entity(authenticated_client)

        response = authenticated_client.get(self.endpoints.list)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify our created entity is in the list
        entity_ids = [entity[self.id_field] for entity in data]
        assert created_entity[self.id_field] in entity_ids

    def test_list_entities_pagination(self, authenticated_client: TestClient):
        """Test entity list pagination"""
        self.create_entity(authenticated_client)

        # Test with limit
        response = authenticated_client.get(f"{self.endpoints.list}?limit=1")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 1

        # Test with skip
        response = authenticated_client.get(f"{self.endpoints.list}?skip=0&limit=10")
        assert response.status_code == status.HTTP_200_OK

    def test_list_entities_sorting(self, authenticated_client: TestClient):
        """Test entity list sorting"""
        self.create_entity(authenticated_client)

        # Test ascending sort by name
        response = authenticated_client.get(f"{self.endpoints.list}?sort_by={self.name_field}&sort_order=asc")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

        # Test descending sort by created_at (default)
        response = authenticated_client.get(f"{self.endpoints.list}?sort_by=created_at&sort_order=desc")
        assert response.status_code == status.HTTP_200_OK

    def test_list_entities_invalid_pagination(self, authenticated_client: TestClient):
        """Test entity list with invalid pagination parameters"""
        # Test negative limit
        response = authenticated_client.get(f"{self.endpoints.list}?limit=-1")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

        # Test negative skip
        response = authenticated_client.get(f"{self.endpoints.list}?skip=-1")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

    def test_list_entities_filter_by_user(self, authenticated_client: TestClient, db_authenticated_user):
        """Test filtering entities by user relationship fields"""
        if not self.has_user_relationships():
            pytest.skip(f"{self.entity_name} does not have user relationship fields")

        # Use valid user ID from fixture
        test_user_id = str(db_authenticated_user.id)

        # Create entity with specific user
        user_entity_data = self.get_sample_data_with_users(
            user_id=test_user_id,
            owner_id=test_user_id,
            assignee_id=test_user_id
        )
        created_entity = self.create_entity(authenticated_client, user_entity_data)

        # Test filtering by various user fields (if supported by backend)
        user_fields = self.get_user_fields()
        for field in user_fields:
            # Try filtering by user field
            response = authenticated_client.get(f"{self.endpoints.list}?{field}={test_user_id}")

            # Should return success (backend may or may not support filtering)
            assert response.status_code == status.HTTP_200_OK

            # If filtering is supported, our entity should be in the results
            data = response.json()
            assert isinstance(data, list)
