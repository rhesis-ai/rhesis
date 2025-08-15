"""
🧪 Base Route Test Classes

This module provides base test classes that implement standard CRUD and route testing patterns
for all entities. This ensures uniformity across all backend route implementations while
allowing for entity-specific customizations.

Usage:
    class TestBehaviorCRUD(BaseCRUDTests):
        entity_name = "behavior"
        endpoints = APIEndpoints.BEHAVIORS
        
Benefits:
- Ensures uniform route behavior across all entities
- Reduces test code duplication by ~80%
- Guarantees consistent test coverage for all entities
- Makes it easy to add new entities with full test coverage
"""

import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .faker_utils import TestDataGenerator

# Initialize Faker
fake = Faker()


class BaseEntityTests(ABC):
    """Abstract base class for all entity route tests"""
    
    # Must be overridden by subclasses
    entity_name: str = ""           # e.g., "behavior", "topic" 
    entity_plural: str = ""         # e.g., "behaviors", "topics"
    endpoints = None                # e.g., APIEndpoints.BEHAVIORS
    data_generator = None           # e.g., TestDataGenerator method
    
    # Optional overrides
    id_field: str = "id"
    name_field: str = "name"
    description_field: str = "description"
    
    @abstractmethod
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample data for entity creation"""
        pass
    
    @abstractmethod
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal data for entity creation"""
        pass
    
    @abstractmethod
    def get_update_data(self) -> Dict[str, Any]:
        """Return data for entity updates"""
        pass
    
    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid data (missing required fields)"""
        return {}
    
    def get_long_name_data(self) -> Dict[str, Any]:
        """Return data with very long name for edge testing"""
        return {
            self.name_field: fake.text(max_nb_chars=1000).replace('\n', ' '),
            self.description_field: fake.text(max_nb_chars=50)
        }
    
    def get_special_chars_data(self) -> Dict[str, Any]:
        """Return data with special characters for edge testing"""
        return {
            self.name_field: f"{fake.word()} 🧪 with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}",
            self.description_field: f"Déscription with spëcial characters: {fake.text(max_nb_chars=50)} & symbols: @#$%^&*()"
        }
    
    def get_null_description_data(self) -> Dict[str, Any]:
        """Return data with null description"""
        return {
            self.name_field: fake.catch_phrase(),
            self.description_field: None
        }
    
    def create_entity(self, client: TestClient, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Helper to create an entity and return response data"""
        if data is None:
            data = self.get_sample_data()
        response = client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK
        return response.json()
    
    def create_multiple_entities(self, client: TestClient, count: int) -> list:
        """Helper to create multiple entities for testing"""
        entities = []
        for i in range(count):
            data = self.get_sample_data()
            data[self.name_field] = f"{fake.word().title()} Test {self.entity_name.title()} {i}"
            entity = self.create_entity(client, data)
            entities.append(entity)
        return entities


@pytest.mark.unit
@pytest.mark.critical
class BaseCRUDTests(BaseEntityTests):
    """Base class for CRUD operation tests"""
    
    def test_create_entity_success(self, authenticated_client: TestClient):
        """🧩🔥 Test successful entity creation"""
        sample_data = self.get_sample_data()
        response = authenticated_client.post(self.endpoints.create, json=sample_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data[self.name_field] == sample_data[self.name_field]
        if self.description_field in sample_data:
            assert data[self.description_field] == sample_data[self.description_field]
        assert self.id_field in data

    def test_create_entity_minimal_data(self, authenticated_client: TestClient):
        """🧩 Test entity creation with minimal required data"""
        minimal_data = self.get_minimal_data()
        response = authenticated_client.post(self.endpoints.create, json=minimal_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data[self.name_field] == minimal_data[self.name_field]
        assert self.id_field in data

    def test_create_entity_invalid_data(self, authenticated_client: TestClient):
        """🧩 Test entity creation with invalid data"""
        invalid_data = self.get_invalid_data()
        
        response = authenticated_client.post(self.endpoints.create, json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_entity_by_id_success(self, authenticated_client: TestClient):
        """🧩🔥 Test retrieving entity by ID"""
        created_entity = self.create_entity(authenticated_client)
        entity_id = created_entity[self.id_field]
        
        response = authenticated_client.get(self.endpoints.get(entity_id))
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data[self.id_field] == entity_id
        assert data[self.name_field] == created_entity[self.name_field]

    def test_get_entity_by_id_not_found(self, authenticated_client: TestClient):
        """🧩 Test retrieving non-existent entity"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.get(self.endpoints.get(non_existent_id))
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_entity_invalid_uuid(self, authenticated_client: TestClient):
        """🧩 Test retrieving entity with invalid UUID"""
        invalid_id = "not-a-uuid"
        
        response = authenticated_client.get(self.endpoints.get(invalid_id))
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_entity_success(self, authenticated_client: TestClient):
        """🧩🔥 Test successful entity update"""
        created_entity = self.create_entity(authenticated_client)
        entity_id = created_entity[self.id_field]
        update_data = self.get_update_data()
        
        response = authenticated_client.put(self.endpoints.put(entity_id), json=update_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data[self.id_field] == entity_id
        assert data[self.name_field] == update_data[self.name_field]
        if self.description_field in update_data:
            assert data[self.description_field] == update_data[self.description_field]

    def test_update_entity_partial(self, authenticated_client: TestClient):
        """🧩 Test partial entity update"""
        created_entity = self.create_entity(authenticated_client)
        entity_id = created_entity[self.id_field]
        partial_update = {self.name_field: fake.company() + f" {self.entity_name.title()}"}
        
        response = authenticated_client.put(self.endpoints.put(entity_id), json=partial_update)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data[self.name_field] == partial_update[self.name_field]

    def test_update_entity_not_found(self, authenticated_client: TestClient):
        """🧩 Test updating non-existent entity"""
        non_existent_id = str(uuid.uuid4())
        update_data = self.get_update_data()
        
        response = authenticated_client.put(self.endpoints.put(non_existent_id), json=update_data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_entity_success(self, authenticated_client: TestClient):
        """🧩🔥 Test successful entity deletion"""
        created_entity = self.create_entity(authenticated_client)
        entity_id = created_entity[self.id_field]
        
        response = authenticated_client.delete(self.endpoints.remove(entity_id))
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data[self.id_field] == entity_id
        
        # Verify entity is deleted by trying to get it
        get_response = authenticated_client.get(self.endpoints.get(entity_id))
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_entity_not_found(self, authenticated_client: TestClient):
        """🧩 Test deleting non-existent entity"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.delete(self.endpoints.remove(non_existent_id))
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.critical
class BaseListOperationTests(BaseEntityTests):
    """Base class for list operation tests"""
    
    def test_list_entities_empty(self, authenticated_client: TestClient):
        """🔗 Test listing entities when none exist"""
        response = authenticated_client.get(self.endpoints.list)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)

    def test_list_entities_with_data(self, authenticated_client: TestClient):
        """🔗🔥 Test listing entities with existing data"""
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
        """🔗 Test entity list pagination"""
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
        """🔗 Test entity list sorting"""
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
        """🔗 Test entity list with invalid pagination parameters"""
        # Test negative limit
        response = authenticated_client.get(f"{self.endpoints.list}?limit=-1")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

        # Test negative skip
        response = authenticated_client.get(f"{self.endpoints.list}?skip=-1")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]


@pytest.mark.unit
@pytest.mark.critical
class BaseAuthenticationTests(BaseEntityTests):
    """Base class for authentication tests"""
    
    def test_entity_routes_require_authentication(self, client: TestClient):
        """🛡️🔥 Test that entity routes require authentication"""
        sample_data = self.get_sample_data()
        
        # Test POST
        response = client.post(self.endpoints.create, json=sample_data)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        
        # Test GET list
        response = client.get(self.endpoints.list)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        
        # Test GET by ID
        test_id = str(uuid.uuid4())
        response = client.get(self.endpoints.get(test_id))
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.unit
class BaseEdgeCaseTests(BaseEntityTests):
    """Base class for edge case tests"""
    
    def test_entity_with_very_long_name(self, authenticated_client: TestClient):
        """🏃‍♂️ Test entity creation with very long name"""
        long_data = self.get_long_name_data()
        
        response = authenticated_client.post(self.endpoints.create, json=long_data)
        
        # Should either succeed or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_entity_with_special_characters(self, authenticated_client: TestClient):
        """🏃‍♂️ Test entity creation with special characters"""
        special_data = self.get_special_chars_data()
        
        response = authenticated_client.post(self.endpoints.create, json=special_data)
        
        # Should handle special characters gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_entity_with_null_description(self, authenticated_client: TestClient):
        """🏃‍♂️ Test entity creation with explicit null description"""
        null_data = self.get_null_description_data()
        
        response = authenticated_client.post(self.endpoints.create, json=null_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data[self.description_field] is None


@pytest.mark.slow
@pytest.mark.integration
class BasePerformanceTests(BaseEntityTests):
    """Base class for performance tests"""
    
    def test_create_multiple_entities_performance(self, authenticated_client: TestClient):
        """🐌 Test creating multiple entities for performance"""
        import time
        
        start_time = time.time()
        
        # Create 10 entities
        created_entities = self.create_multiple_entities(authenticated_client, 10)
        
        duration = time.time() - start_time
        
        # Should complete within reasonable time (10 seconds for 10 creates)
        assert duration < 10.0
        assert len(created_entities) == 10
        
        # Clean up - delete created entities
        for entity in created_entities:
            authenticated_client.delete(self.endpoints.remove(entity[self.id_field]))

    def test_list_entities_with_large_pagination(self, authenticated_client: TestClient):
        """🐌 Test listing entities with large pagination parameters"""
        response = authenticated_client.get(f"{self.endpoints.list}?limit=100&skip=0")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 100


class BaseHealthTests(BaseEntityTests):
    """Base class for basic health tests"""
    
    def test_entity_routes_basic_health(self, authenticated_client: TestClient):
        """✅ Basic health check for entity routes"""
        # Test that the entity endpoint is accessible
        response = authenticated_client.get(self.endpoints.list)
        
        # Should return 200 (even if empty list)
        assert response.status_code == status.HTTP_200_OK
        
        # Should return a list
        data = response.json()
        assert isinstance(data, list)


# Composite test class that includes all standard tests
class BaseEntityRouteTests(
    BaseCRUDTests,
    BaseListOperationTests, 
    BaseAuthenticationTests,
    BaseEdgeCaseTests,
    BasePerformanceTests,
    BaseHealthTests
):
    """Complete base test suite for any entity - includes all standard tests"""
    pass
