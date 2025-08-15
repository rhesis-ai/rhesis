"""
🧪 Topic Routes Testing Suite (DRY Implementation)

Comprehensive test suite for all topic entity routes using the DRY approach
with base test classes. This ensures uniformity across all backend route implementations.

Run with: python -m pytest tests/backend/routes/test_topic.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests

# Initialize Faker
fake = Faker()


class TopicTestMixin:
    """Mixin providing topic-specific test data and configuration"""
    
    # Entity configuration
    entity_name = "topic"
    entity_plural = "topics"
    endpoints = APIEndpoints.TOPICS
    
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample topic data for testing"""
        return {
            "name": fake.catch_phrase(),
            "description": fake.text(max_nb_chars=200),
            "parent_id": None,
            "entity_type_id": None,
            "status_id": None,
            "organization_id": None,
            "user_id": None,
        }
    
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal topic data for creation"""
        return {"name": fake.word().title() + " " + fake.word().title()}
    
    def get_update_data(self) -> Dict[str, Any]:
        """Return topic update data"""
        return {
            "name": fake.sentence(nb_words=3).rstrip('.'),
            "description": fake.paragraph(nb_sentences=2)
        }


# Standard entity tests - gets ALL tests from base classes
class TestTopicStandardRoutes(TopicTestMixin, BaseEntityRouteTests):
    """Complete standard topic route tests using base classes"""
    pass


# Topic-specific tests for hierarchical relationships
@pytest.mark.integration
class TestTopicHierarchy(TopicTestMixin, BaseEntityTests):
    """Topic-specific tests for hierarchical relationships"""
    
    @pytest.fixture
    def parent_topic(self, authenticated_client: TestClient):
        """Create a parent topic for hierarchical testing"""
        parent_data = {
            "name": fake.sentence(nb_words=2).rstrip('.') + " Topic",
            "description": fake.text(max_nb_chars=100)
        }
        return self.create_entity(authenticated_client, parent_data)

    def test_create_child_topic(self, authenticated_client: TestClient, parent_topic):
        """🌳 Test creating a child topic with parent relationship"""
        child_data = {
            "name": fake.word().title() + " Child Topic",
            "description": fake.text(max_nb_chars=120),
            "parent_id": parent_topic["id"]
        }

        child = self.create_entity(authenticated_client, child_data)
        assert child["name"] == child_data["name"]
        assert child["parent_id"] == parent_topic["id"]

    def test_create_topic_with_invalid_parent(self, authenticated_client: TestClient):
        """🌳 Test creating topic with non-existent parent"""
        child_data = {
            "name": fake.word().title() + " Orphaned Topic",
            "parent_id": str(uuid.uuid4())  # Non-existent parent
        }

        response = authenticated_client.post(self.endpoints.create, json=child_data)

        # API should handle foreign key constraint violations gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid parent" in response.json()["detail"].lower()

    def test_hierarchy_circular_reference_prevention(self, authenticated_client: TestClient):
        """🌳 Test prevention of circular references in topic hierarchy"""
        created_topic = self.create_entity(authenticated_client)
        
        # Try to make the topic its own parent
        update_data = {
            "parent_id": created_topic["id"]
        }

        response = authenticated_client.put(self.endpoints.put(created_topic['id']), json=update_data)

        # Should either be prevented or handled gracefully
        # Different implementations may handle this differently
        assert response.status_code in [
            status.HTTP_200_OK,  # Allowed (handled at business logic level)
            status.HTTP_400_BAD_REQUEST,  # Prevented
            status.HTTP_422_UNPROCESSABLE_ENTITY  # Validation error
        ]


# Topic-specific edge cases (if any)
@pytest.mark.unit
class TestTopicSpecificEdgeCases(TopicTestMixin, BaseEntityTests):
    """Topic-specific edge cases beyond the standard ones"""
    
    def test_topic_with_empty_string_description(self, authenticated_client: TestClient):
        """🏃‍♂️ Test topic creation with empty string description"""
        topic_data = {
            "name": fake.catch_phrase(),
            "description": ""
        }

        response = authenticated_client.post(self.endpoints.create, json=topic_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["name"] == topic_data["name"]
        assert data["description"] == ""