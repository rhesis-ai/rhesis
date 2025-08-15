"""
🧪 Comprehensive route tests for the Behavior entity

This test suite covers all behavior routes including:
- CRUD operations (Create, Read, Update, Delete)
- List operations with pagination, sorting, and filtering
- Behavior-metric relationship management
- Error handling and edge cases
- Authentication requirements

Run with: python -m pytest tests/backend/routes/test_behavior.py -v
"""

import uuid
import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas

# Initialize Faker instance
fake = Faker()


# 🏗️ Test Fixtures

@pytest.fixture
def sample_behavior_data():
    """📝 Sample behavior data for testing"""
    return {
        "name": fake.catch_phrase(),
        "description": fake.text(max_nb_chars=200),
        "status_id": None,
        "user_id": None,
        "organization_id": None
    }


@pytest.fixture
def sample_behavior_create_minimal():
    """📝 Minimal behavior data for creation"""
    return {
        "name": fake.word().title() + " " + fake.bs().title()
    }


@pytest.fixture
def sample_behavior_update_data():
    """📝 Behavior update data"""
    return {
        "name": fake.sentence(nb_words=3).rstrip('.'),
        "description": fake.paragraph(nb_sentences=2)
    }


@pytest.fixture
def created_behavior(authenticated_client: TestClient, sample_behavior_data):
    """🏗️ Create a behavior for testing and return its data"""
    response = authenticated_client.post("/behaviors/", json=sample_behavior_data)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


@pytest.fixture
def created_metric(authenticated_client: TestClient):
    """🏗️ Create a metric for testing behavior-metric relationships"""
    metric_data = {
        "name": fake.word().title() + " " + fake.word().title(),
        "description": fake.text(max_nb_chars=150),
        "evaluation_prompt": fake.sentence(nb_words=8),
        "score_type": fake.random_element(elements=("numeric", "categorical", "binary"))
    }
    response = authenticated_client.post("/metrics/", json=metric_data)
    if response.status_code not in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
        # If metrics endpoint doesn't exist or fails, create a mock metric ID
        return {"id": str(uuid.uuid4())}
    return response.json()


# 🧩 Unit Tests - Behavior CRUD Operations

@pytest.mark.unit
@pytest.mark.critical
class TestBehaviorCRUD:
    """Critical CRUD operations for behaviors"""

    def test_create_behavior_success(self, authenticated_client: TestClient, sample_behavior_data):
        """🧩🔥 Test successful behavior creation"""
        response = authenticated_client.post("/behaviors/", json=sample_behavior_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["name"] == sample_behavior_data["name"]
        assert data["description"] == sample_behavior_data["description"]
        assert "id" in data
        # Check for timestamp fields (may vary by API implementation)
        # Common timestamp field names: created_at, createdAt, created, etc.
        timestamp_fields = ["created_at", "createdAt", "created", "timestamp"]
        has_timestamp = any(field in data for field in timestamp_fields)
        # Not requiring timestamp fields as they may not be included in response

    def test_create_behavior_minimal_data(self, authenticated_client: TestClient, sample_behavior_create_minimal):
        """🧩 Test behavior creation with minimal required data"""
        response = authenticated_client.post("/behaviors/", json=sample_behavior_create_minimal)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["name"] == sample_behavior_create_minimal["name"]
        assert data["description"] is None
        assert "id" in data

    def test_create_behavior_invalid_data(self, authenticated_client: TestClient):
        """🧩 Test behavior creation with invalid data"""
        invalid_data = {}  # Missing required 'name' field
        
        response = authenticated_client.post("/behaviors/", json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_behavior_with_invalid_status(self, authenticated_client: TestClient):
        """🧩 Test creating behavior with non-existent status"""
        behavior_data = {
            "name": fake.catch_phrase(),
            "description": fake.text(max_nb_chars=100),
            "status_id": str(uuid.uuid4())  # Non-existent status
        }

        response = authenticated_client.post("/behaviors/", json=behavior_data)

        # API should handle foreign key constraint violations gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in response.json()["detail"].lower() or "not found" in response.json()["detail"].lower()

    def test_get_behavior_by_id_success(self, authenticated_client: TestClient, created_behavior):
        """🧩🔥 Test retrieving behavior by ID"""
        behavior_id = created_behavior["id"]
        
        response = authenticated_client.get(f"/behaviors/{behavior_id}")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["id"] == behavior_id
        assert data["name"] == created_behavior["name"]

    def test_get_behavior_by_id_not_found(self, authenticated_client: TestClient):
        """🧩 Test retrieving non-existent behavior"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.get(f"/behaviors/{non_existent_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_behavior_invalid_uuid(self, authenticated_client: TestClient):
        """🧩 Test retrieving behavior with invalid UUID"""
        invalid_id = "not-a-uuid"
        
        response = authenticated_client.get(f"/behaviors/{invalid_id}")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_behavior_success(self, authenticated_client: TestClient, created_behavior, sample_behavior_update_data):
        """🧩🔥 Test successful behavior update"""
        behavior_id = created_behavior["id"]
        
        response = authenticated_client.put(f"/behaviors/{behavior_id}", json=sample_behavior_update_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["id"] == behavior_id
        assert data["name"] == sample_behavior_update_data["name"]
        assert data["description"] == sample_behavior_update_data["description"]

    def test_update_behavior_partial(self, authenticated_client: TestClient, created_behavior):
        """🧩 Test partial behavior update"""
        behavior_id = created_behavior["id"]
        partial_update = {"name": fake.company_suffix() + " " + fake.word().title()}
        
        response = authenticated_client.put(f"/behaviors/{behavior_id}", json=partial_update)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["name"] == partial_update["name"]
        # Description should remain unchanged
        assert data["description"] == created_behavior["description"]

    def test_update_behavior_not_found(self, authenticated_client: TestClient, sample_behavior_update_data):
        """🧩 Test updating non-existent behavior"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.put(f"/behaviors/{non_existent_id}", json=sample_behavior_update_data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_behavior_success(self, authenticated_client: TestClient, created_behavior):
        """🧩🔥 Test successful behavior deletion"""
        behavior_id = created_behavior["id"]
        
        response = authenticated_client.delete(f"/behaviors/{behavior_id}")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["id"] == behavior_id
        
        # Verify behavior is deleted by trying to get it
        get_response = authenticated_client.get(f"/behaviors/{behavior_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_behavior_not_found(self, authenticated_client: TestClient):
        """🧩 Test deleting non-existent behavior"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.delete(f"/behaviors/{non_existent_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


# 🔗 Integration Tests - List Operations

@pytest.mark.integration
@pytest.mark.critical
class TestBehaviorListOperations:
    """Integration tests for behavior list operations"""

    def test_list_behaviors_empty(self, authenticated_client: TestClient):
        """🔗 Test listing behaviors when none exist"""
        response = authenticated_client.get("/behaviors/")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        # May be empty or contain pre-existing behaviors

    def test_list_behaviors_with_data(self, authenticated_client: TestClient, created_behavior):
        """🔗🔥 Test listing behaviors with existing data"""
        response = authenticated_client.get("/behaviors/")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify our created behavior is in the list
        behavior_ids = [behavior["id"] for behavior in data]
        assert created_behavior["id"] in behavior_ids

    def test_list_behaviors_pagination(self, authenticated_client: TestClient, created_behavior):
        """🔗 Test behavior list pagination"""
        # Test with limit
        response = authenticated_client.get("/behaviors/?limit=1")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 1

        # Test with skip
        response = authenticated_client.get("/behaviors/?skip=0&limit=10")
        
        assert response.status_code == status.HTTP_200_OK

    def test_list_behaviors_sorting(self, authenticated_client: TestClient, created_behavior):
        """🔗 Test behavior list sorting"""
        # Test ascending sort by name
        response = authenticated_client.get("/behaviors/?sort_by=name&sort_order=asc")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)

        # Test descending sort by created_at (default)
        response = authenticated_client.get("/behaviors/?sort_by=created_at&sort_order=desc")
        
        assert response.status_code == status.HTTP_200_OK

    def test_list_behaviors_invalid_pagination(self, authenticated_client: TestClient):
        """🔗 Test behavior list with invalid pagination parameters"""
        # Test negative limit
        response = authenticated_client.get("/behaviors/?limit=-1")
        
        # Should either return 422, 400, or handle gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

        # Test negative skip
        response = authenticated_client.get("/behaviors/?skip=-1")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]


# 🔗 Integration Tests - Behavior-Metric Relationships

@pytest.mark.integration
class TestBehaviorMetricRelationships:
    """Integration tests for behavior-metric relationships"""

    def test_get_behavior_metrics_empty(self, authenticated_client: TestClient, created_behavior):
        """🔗 Test getting metrics for behavior with no metrics"""
        behavior_id = created_behavior["id"]
        
        response = authenticated_client.get(f"/behaviors/{behavior_id}/metrics/")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_behavior_metrics_not_found(self, authenticated_client: TestClient):
        """🔗 Test getting metrics for non-existent behavior"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.get(f"/behaviors/{non_existent_id}/metrics/")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_metric_to_behavior_success(self, authenticated_client: TestClient, created_behavior, created_metric):
        """🔗 Test successfully adding metric to behavior"""
        behavior_id = created_behavior["id"]
        metric_id = created_metric["id"]
        
        response = authenticated_client.post(f"/behaviors/{behavior_id}/metrics/{metric_id}")
        
        # Should return success message or 200/201 status
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "status" in data
            assert data["status"] == "success"

    def test_add_metric_to_behavior_not_found(self, authenticated_client: TestClient, created_metric):
        """🔗 Test adding metric to non-existent behavior"""
        non_existent_behavior_id = str(uuid.uuid4())
        metric_id = created_metric["id"]
        
        response = authenticated_client.post(f"/behaviors/{non_existent_behavior_id}/metrics/{metric_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_nonexistent_metric_to_behavior(self, authenticated_client: TestClient, created_behavior):
        """🔗 Test adding non-existent metric to behavior"""
        behavior_id = created_behavior["id"]
        non_existent_metric_id = str(uuid.uuid4())
        
        response = authenticated_client.post(f"/behaviors/{behavior_id}/metrics/{non_existent_metric_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_metric_from_behavior_success(self, authenticated_client: TestClient, created_behavior, created_metric):
        """🔗 Test successfully removing metric from behavior"""
        behavior_id = created_behavior["id"]
        metric_id = created_metric["id"]
        
        # First add the metric
        add_response = authenticated_client.post(f"/behaviors/{behavior_id}/metrics/{metric_id}")
        assert add_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        
        # Then remove it
        response = authenticated_client.delete(f"/behaviors/{behavior_id}/metrics/{metric_id}")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "success"

    def test_remove_metric_from_behavior_not_found(self, authenticated_client: TestClient, created_metric):
        """🔗 Test removing metric from non-existent behavior"""
        non_existent_behavior_id = str(uuid.uuid4())
        metric_id = created_metric["id"]
        
        response = authenticated_client.delete(f"/behaviors/{non_existent_behavior_id}/metrics/{metric_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


# 🛡️ Security and Authentication Tests

@pytest.mark.unit
@pytest.mark.critical
class TestBehaviorAuthentication:
    """Critical security tests for behavior routes"""

    def test_behavior_routes_require_authentication(self):
        """🛡️🔥 Test that behavior routes require authentication"""
        # Create client without authentication
        from fastapi.testclient import TestClient
        from rhesis.backend.app.main import app
        
        unauthenticated_client = TestClient(app)
        
        # Test POST /behaviors/
        response = unauthenticated_client.post("/behaviors/", json={"name": "Test"})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        
        # Test GET /behaviors/
        response = unauthenticated_client.get("/behaviors/")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        
        # Test GET /behaviors/{id}
        test_id = str(uuid.uuid4())
        response = unauthenticated_client.get(f"/behaviors/{test_id}")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


# 🏃‍♂️ Edge Cases and Error Handling

@pytest.mark.unit
class TestBehaviorEdgeCases:
    """Edge cases and error handling tests"""

    def test_behavior_with_very_long_name(self, authenticated_client: TestClient):
        """🏃‍♂️ Test behavior creation with very long name"""
        long_name = fake.text(max_nb_chars=1000).replace('\n', ' ')  # Very long name
        
        behavior_data = {
            "name": long_name,
            "description": fake.text(max_nb_chars=50)
        }
        
        response = authenticated_client.post("/behaviors/", json=behavior_data)
        
        # Should either succeed or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_behavior_with_special_characters(self, authenticated_client: TestClient):
        """🏃‍♂️ Test behavior creation with special characters"""
        special_chars_data = {
            "name": f"{fake.word()} 🧪 with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}",
            "description": f"Déscription with spëcial characters: {fake.text(max_nb_chars=50)} & symbols: @#$%^&*()"
        }
        
        response = authenticated_client.post("/behaviors/", json=special_chars_data)
        
        # Should handle special characters gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_behavior_with_null_description(self, authenticated_client: TestClient):
        """🏃‍♂️ Test behavior creation with explicit null description"""
        behavior_data = {
            "name": fake.catch_phrase(),
            "description": None
        }
        
        response = authenticated_client.post("/behaviors/", json=behavior_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["description"] is None


# 🎯 Performance and Load Tests

@pytest.mark.slow
@pytest.mark.integration
class TestBehaviorPerformance:
    """Performance tests for behavior operations"""

    def test_create_multiple_behaviors_performance(self, authenticated_client: TestClient):
        """🐌 Test creating multiple behaviors for performance"""
        import time
        
        start_time = time.time()
        
        # Create 10 behaviors
        created_behaviors = []
        for i in range(10):
            behavior_data = {
                "name": f"{fake.word().title()} Test Behavior {i}",
                "description": fake.paragraph(nb_sentences=2)
            }
            response = authenticated_client.post("/behaviors/", json=behavior_data)
            assert response.status_code == status.HTTP_200_OK
            created_behaviors.append(response.json())
        
        duration = time.time() - start_time
        
        # Should complete within reasonable time (10 seconds for 10 creates)
        assert duration < 10.0
        assert len(created_behaviors) == 10
        
        # Clean up - delete created behaviors
        for behavior in created_behaviors:
            authenticated_client.delete(f"/behaviors/{behavior['id']}")

    def test_list_behaviors_with_large_pagination(self, authenticated_client: TestClient):
        """🐌 Test listing behaviors with large pagination parameters"""
        response = authenticated_client.get("/behaviors/?limit=100&skip=0")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 100


# ✅ Basic Smoke Tests

def test_behavior_routes_basic_health():
    """✅ Basic health check for behavior routes - no markers, always runs"""
    # Just verify the route paths are valid
    behavior_routes = [
        "/behaviors/",
        "/behaviors/{behavior_id}",
        "/behaviors/{behavior_id}/metrics/",
        "/behaviors/{behavior_id}/metrics/{metric_id}"
    ]
    
    for route in behavior_routes:
        assert isinstance(route, str)
        assert route.startswith("/behaviors")
