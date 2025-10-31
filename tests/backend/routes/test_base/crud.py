"""
🧩 CRUD Operation Tests

This module provides comprehensive CRUD (Create, Read, Update, Delete) operation tests
for all entities. Tests standard operations like creating, retrieving, updating, and deleting entities.
"""

import uuid

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .core import BaseEntityTests

# Initialize Faker
fake = Faker()


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
        
        # Verify entity is soft-deleted by trying to get it (should return 410 GONE)
        get_response = authenticated_client.get(self.endpoints.get(entity_id))
        assert get_response.status_code == status.HTTP_410_GONE

    def test_delete_entity_not_found(self, authenticated_client: TestClient):
        """🧩 Test deleting non-existent entity"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.delete(self.endpoints.remove(non_existent_id))
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
