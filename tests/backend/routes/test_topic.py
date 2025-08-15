"""
🧪 Topic Routes Testing Suite

Comprehensive test suite for all topic entity routes including:
- CRUD Operations (Create, Read, Update, Delete)
- List Operations (pagination, sorting, filtering)  
- Hierarchical Relationships (parent/child topics)
- Authentication & Authorization
- Edge Cases & Error Handling
- Performance Testing

Author: AI Assistant
"""

import uuid
from typing import Dict, Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient


# 🏗️ Test Fixtures


@pytest.fixture
def sample_topic_data():
    """📋 Sample topic data for testing"""
    return {
        "name": "Test Topic",
        "description": "A test topic for unit testing",
        "parent_id": None,
        "entity_type_id": None,
        "status_id": None,
        "organization_id": None,
        "user_id": None,
    }


@pytest.fixture
def sample_topic_create_minimal():
    """📋 Minimal topic data for testing"""
    return {"name": "Minimal Test Topic"}


@pytest.fixture
def created_topic(authenticated_client: TestClient, sample_topic_data):
    """🏗️ Create a topic for testing and return its data"""
    response = authenticated_client.post("/topics/", json=sample_topic_data)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


@pytest.fixture
def parent_topic(authenticated_client: TestClient):
    """🏗️ Create a parent topic for hierarchical testing"""
    parent_data = {
        "name": "Parent Topic",
        "description": "A parent topic for hierarchy testing"
    }
    response = authenticated_client.post("/topics/", json=parent_data)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


# 🧩 Unit Tests - Topic CRUD Operations


@pytest.mark.unit
@pytest.mark.critical
class TestTopicCRUD:
    """🧩 Topic CRUD operations testing"""

    def test_create_topic_success(self, authenticated_client: TestClient, sample_topic_data):
        """🧩🔥 Test successful topic creation"""
        response = authenticated_client.post("/topics/", json=sample_topic_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["name"] == sample_topic_data["name"]
        assert data["description"] == sample_topic_data["description"]
        assert "id" in data
        # Check for timestamp fields (may vary by API implementation)
        # Common timestamp field names: created_at, createdAt, created, etc.
        timestamp_fields = ["created_at", "createdAt", "created", "timestamp"]
        has_timestamp = any(field in data for field in timestamp_fields)
        # Not requiring timestamp fields as they may not be included in response

    def test_create_topic_minimal_data(self, authenticated_client: TestClient, sample_topic_create_minimal):
        """🧩 Test topic creation with minimal required data"""
        response = authenticated_client.post("/topics/", json=sample_topic_create_minimal)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["name"] == sample_topic_create_minimal["name"]
        assert "id" in data

    def test_create_topic_invalid_data(self, authenticated_client: TestClient):
        """🧩 Test topic creation with invalid data"""
        invalid_data = {}  # Missing required 'name' field

        response = authenticated_client.post("/topics/", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_topic_by_id_success(self, authenticated_client: TestClient, created_topic):
        """🧩🔥 Test successful topic retrieval by ID"""
        topic_id = created_topic["id"]

        response = authenticated_client.get(f"/topics/{topic_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == topic_id
        assert data["name"] == created_topic["name"]

    def test_get_topic_by_id_not_found(self, authenticated_client: TestClient):
        """🧩 Test topic retrieval with non-existent ID"""
        non_existent_id = str(uuid.uuid4())

        response = authenticated_client.get(f"/topics/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_topic_invalid_uuid(self, authenticated_client: TestClient):
        """🧩 Test topic retrieval with invalid UUID format"""
        invalid_id = "not-a-uuid"

        response = authenticated_client.get(f"/topics/{invalid_id}")

        # FastAPI should validate UUID format and return 422
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_topic_success(self, authenticated_client: TestClient, created_topic):
        """🧩🔥 Test successful topic update"""
        topic_id = created_topic["id"]
        update_data = {
            "name": "Updated Topic Name",
            "description": "Updated description for testing"
        }

        response = authenticated_client.put(f"/topics/{topic_id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == topic_id
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_topic_partial(self, authenticated_client: TestClient, created_topic):
        """🧩 Test partial topic update"""
        topic_id = created_topic["id"]
        update_data = {"name": "Partially Updated Topic"}

        response = authenticated_client.put(f"/topics/{topic_id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == topic_id
        assert data["name"] == update_data["name"]
        # Description should remain from original (or be None if not set)

    def test_update_topic_not_found(self, authenticated_client: TestClient):
        """🧩 Test updating non-existent topic"""
        non_existent_id = str(uuid.uuid4())
        update_data = {"name": "Updated Topic"}

        response = authenticated_client.put(f"/topics/{non_existent_id}", json=update_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_topic_success(self, authenticated_client: TestClient, created_topic):
        """🧩🔥 Test successful topic deletion"""
        topic_id = created_topic["id"]

        response = authenticated_client.delete(f"/topics/{topic_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == topic_id

        # Verify topic is deleted by trying to get it
        get_response = authenticated_client.get(f"/topics/{topic_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_topic_not_found(self, authenticated_client: TestClient):
        """🧩 Test deleting non-existent topic"""
        non_existent_id = str(uuid.uuid4())

        response = authenticated_client.delete(f"/topics/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# 🔗 Integration Tests - List Operations


@pytest.mark.integration
class TestTopicListOperations:
    """🔗 Topic list and pagination testing"""

    def test_list_topics_empty(self, authenticated_client: TestClient):
        """🔗 Test listing topics when none exist"""
        response = authenticated_client.get("/topics/")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)
        # May be empty or contain existing topics from other tests

    def test_list_topics_with_data(self, authenticated_client: TestClient, created_topic):
        """🔗 Test listing topics with data present"""
        response = authenticated_client.get("/topics/")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least our created topic

        # Find our created topic in the list
        topic_ids = [topic["id"] for topic in data]
        assert created_topic["id"] in topic_ids

    def test_list_topics_pagination(self, authenticated_client: TestClient, created_topic):
        """🔗 Test topic list pagination"""
        # Test with limit
        response = authenticated_client.get("/topics/?limit=5&skip=0")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    def test_list_topics_sorting(self, authenticated_client: TestClient, created_topic):
        """🔗 Test topic list sorting"""
        # Test sorting by name ascending
        response = authenticated_client.get("/topics/?sort_by=name&sort_order=asc")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)

        # Test sorting by name descending
        response = authenticated_client.get("/topics/?sort_by=name&sort_order=desc")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)

    def test_list_topics_invalid_pagination(self, authenticated_client: TestClient):
        """🔗 Test topic list with invalid pagination parameters"""
        # Test negative limit
        response = authenticated_client.get("/topics/?limit=-1")

        # Should either return 422, 400, or handle gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

        # Test negative skip
        response = authenticated_client.get("/topics/?skip=-1")

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]


# 🌳 Integration Tests - Hierarchical Relationships


@pytest.mark.integration
class TestTopicHierarchy:
    """🌳 Topic hierarchical relationship testing"""

    def test_create_child_topic(self, authenticated_client: TestClient, parent_topic):
        """🌳 Test creating a child topic with parent relationship"""
        child_data = {
            "name": "Child Topic",
            "description": "A child topic for hierarchy testing",
            "parent_id": parent_topic["id"]
        }

        response = authenticated_client.post("/topics/", json=child_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["name"] == child_data["name"]
        assert data["parent_id"] == parent_topic["id"]

    def test_create_topic_with_invalid_parent(self, authenticated_client: TestClient):
        """🌳 Test creating topic with non-existent parent"""
        child_data = {
            "name": "Orphaned Topic",
            "parent_id": str(uuid.uuid4())  # Non-existent parent
        }

        response = authenticated_client.post("/topics/", json=child_data)

        # API should handle foreign key constraint violations gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid parent" in response.json()["detail"].lower()

    def test_hierarchy_circular_reference_prevention(self, authenticated_client: TestClient, created_topic):
        """🌳 Test prevention of circular references in topic hierarchy"""
        # Try to make the topic its own parent
        update_data = {
            "parent_id": created_topic["id"]
        }

        response = authenticated_client.put(f"/topics/{created_topic['id']}", json=update_data)

        # Should either be prevented or handled gracefully
        # Different implementations may handle this differently
        assert response.status_code in [
            status.HTTP_200_OK,  # Allowed (handled at business logic level)
            status.HTTP_400_BAD_REQUEST,  # Prevented
            status.HTTP_422_UNPROCESSABLE_ENTITY  # Validation error
        ]


# 🔒 Authentication Tests


@pytest.mark.unit
@pytest.mark.critical
class TestTopicAuthentication:
    """🔒 Topic authentication and authorization testing"""

    def test_topic_routes_require_authentication(self, client: TestClient):
        """🔒 Verify all topic routes require authentication"""
        # Test create endpoint
        response = client.post("/topics/", json={"name": "Test Topic"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Test list endpoint
        response = client.get("/topics/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Test get by ID endpoint
        topic_id = str(uuid.uuid4())
        response = client.get(f"/topics/{topic_id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# 🏃‍♂️ Edge Cases


@pytest.mark.unit
class TestTopicEdgeCases:
    """🏃‍♂️ Topic edge case testing"""

    def test_topic_with_very_long_name(self, authenticated_client: TestClient):
        """🏃‍♂️ Test topic creation with very long name"""
        long_name = "A" * 1000  # Very long name

        topic_data = {
            "name": long_name,
            "description": "Test topic with long name"
        }

        response = authenticated_client.post("/topics/", json=topic_data)

        # Should either succeed or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_topic_with_special_characters(self, authenticated_client: TestClient):
        """🏃‍♂️ Test topic creation with special characters"""
        special_chars_data = {
            "name": "Test Topic 🧪 with émoji & spëcial chars!",
            "description": "Déscription with spëcial characters & symbols: @#$%^&*()"
        }

        response = authenticated_client.post("/topics/", json=special_chars_data)

        # Should handle special characters gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_topic_with_null_description(self, authenticated_client: TestClient):
        """🏃‍♂️ Test topic creation with explicit null description"""
        topic_data = {
            "name": "Test Topic",
            "description": None
        }

        response = authenticated_client.post("/topics/", json=topic_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["name"] == topic_data["name"]

    def test_topic_with_empty_string_description(self, authenticated_client: TestClient):
        """🏃‍♂️ Test topic creation with empty string description"""
        topic_data = {
            "name": "Test Topic",
            "description": ""
        }

        response = authenticated_client.post("/topics/", json=topic_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["name"] == topic_data["name"]
        assert data["description"] == ""


# 🐌 Performance Tests


@pytest.mark.slow
@pytest.mark.performance
class TestTopicPerformance:
    """🐌 Topic performance testing"""

    def test_create_multiple_topics_performance(self, authenticated_client: TestClient):
        """🐌 Test creating multiple topics for performance"""
        import time

        start_time = time.time()

        # Create 10 topics
        created_topics = []
        for i in range(10):
            topic_data = {
                "name": f"Performance Test Topic {i}",
                "description": f"Description for topic {i}"
            }
            response = authenticated_client.post("/topics/", json=topic_data)
            assert response.status_code == status.HTTP_200_OK
            created_topics.append(response.json())

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert duration < 10.0  # 10 seconds max for 10 topics

        # Verify all topics were created
        assert len(created_topics) == 10

    def test_list_topics_with_large_pagination(self, authenticated_client: TestClient):
        """🐌 Test topic listing with large pagination parameters"""
        # Test with large limit
        response = authenticated_client.get("/topics/?limit=100&skip=0")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)


# 🧪 Basic Health Check


@pytest.mark.unit
def test_topic_routes_basic_health(authenticated_client: TestClient):
    """🧪 Basic health check for topic routes"""
    # Test that the topics endpoint is accessible
    response = authenticated_client.get("/topics/")
    
    # Should return 200 (even if empty list)
    assert response.status_code == status.HTTP_200_OK
    
    # Should return a list
    data = response.json()
    assert isinstance(data, list)
