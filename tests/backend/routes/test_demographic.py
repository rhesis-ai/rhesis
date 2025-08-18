"""
🧪 Demographic Routes Testing Suite

Comprehensive test suite for all demographic entity routes including dependency relationships
with dimensions. This ensures uniformity across all backend route implementations.

Run with: python -m pytest tests/backend/routes/test_demographic.py -v
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


class DemographicTestMixin:
    """Mixin providing demographic-specific test data and configuration"""
    
    # Entity configuration
    entity_name = "demographic"
    entity_plural = "demographics"
    endpoints = APIEndpoints.DEMOGRAPHICS
    
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample demographic data for testing"""
        return {
            "name": fake.word().title() + " Demographic",
            "description": fake.text(max_nb_chars=200),
            "dimension_id": None,  # Will be set when needed
            "user_id": None,
            "organization_id": None,
        }
    
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal demographic data for creation"""
        return {
            "name": fake.word().title() + " Demographic"
        }
    
    def get_update_data(self) -> Dict[str, Any]:
        """Return demographic update data"""
        return {
            "name": fake.sentence(nb_words=2).rstrip('.') + " Demographic",
            "description": fake.paragraph(nb_sentences=2)
        }
    
    def create_dimension(self, client: TestClient) -> Dict[str, Any]:
        """Helper to create a dimension for demographic testing"""
        dimension_data = {
            "name": fake.word().title() + " Test Dimension",
            "description": fake.text(max_nb_chars=100)
        }
        response = client.post(APIEndpoints.DIMENSIONS.create, json=dimension_data)
        assert response.status_code == status.HTTP_200_OK
        return response.json()


# Standard entity tests - gets ALL tests from base classes
class TestDemographicStandardRoutes(DemographicTestMixin, BaseEntityRouteTests):
    """Complete standard demographic route tests using base classes"""
    pass


# Demographic-specific tests with dimension relationships
@pytest.mark.unit
@pytest.mark.critical
class TestDemographicWithDimensions(DemographicTestMixin, BaseEntityTests):
    """Test demographic functionality with dimension relationships"""
    
    @pytest.fixture
    def sample_dimension(self, authenticated_client: TestClient):
        """Fixture to provide a sample dimension for testing"""
        return self.create_dimension(authenticated_client)
    
    def test_create_demographic_with_dimension(self, authenticated_client: TestClient, sample_dimension):
        """🧩🔥 Test creating demographic with valid dimension relationship"""
        demographic_data = {
            "name": "Age Group 18-25",
            "description": "Young adults demographic",
            "dimension_id": sample_dimension["id"]
        }

        response = authenticated_client.post(self.endpoints.create, json=demographic_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == demographic_data["name"]
        assert data["dimension_id"] == sample_dimension["id"]
        assert data["description"] == demographic_data["description"]
    
    def test_create_demographic_with_invalid_dimension(self, authenticated_client: TestClient):
        """🧩 Test creating demographic with non-existent dimension"""
        demographic_data = {
            "name": "Invalid Dimension Demographic",
            "dimension_id": str(uuid.uuid4())  # Non-existent dimension
        }

        response = authenticated_client.post(self.endpoints.create, json=demographic_data)

        # Should handle foreign key constraint violations gracefully
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            assert "dimension" in response.json()["detail"].lower()
    
    def test_create_demographic_without_dimension(self, authenticated_client: TestClient):
        """🧩 Test creating demographic without dimension (null dimension_id)"""
        demographic_data = {
            "name": "No Dimension Demographic",
            "description": "Demographic without specific dimension",
            "dimension_id": None
        }

        response = authenticated_client.post(self.endpoints.create, json=demographic_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == demographic_data["name"]
        assert data["dimension_id"] is None
    
    def test_update_demographic_dimension_relationship(self, authenticated_client: TestClient, sample_dimension):
        """🧩 Test updating demographic's dimension relationship"""
        # Create demographic without dimension
        demographic_data = {
            "name": "Update Dimension Test",
            "dimension_id": None
        }
        created = self.create_entity(authenticated_client, demographic_data)
        
        # Create another dimension
        new_dimension = self.create_dimension(authenticated_client)
        
        # Update demographic to associate with dimension
        update_data = {
            "dimension_id": new_dimension["id"]
        }
        
        response = authenticated_client.put(self.endpoints.put(created["id"]), json=update_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["dimension_id"] == new_dimension["id"]
        assert data["name"] == created["name"]  # Name should remain unchanged
    
    def test_list_demographics_with_dimension_filter(self, authenticated_client: TestClient, sample_dimension):
        """🧩 Test listing demographics filtered by dimension"""
        # Create demographics with and without dimensions
        demo_with_dim = {
            "name": "With Dimension Demo",
            "dimension_id": sample_dimension["id"]
        }
        demo_without_dim = {
            "name": "Without Dimension Demo",
            "dimension_id": None
        }
        
        self.create_entity(authenticated_client, demo_with_dim)
        self.create_entity(authenticated_client, demo_without_dim)
        
        # Test filtering by dimension (if supported)
        filter_query = f"dimension_id eq '{sample_dimension['id']}'"
        response = authenticated_client.get(f"{self.endpoints.list}?$filter={filter_query}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # The filter may or may not find our demographic depending on implementation


@pytest.mark.unit
class TestDemographicSpecificEdgeCases(DemographicTestMixin, BaseEntityTests):
    """Demographic-specific edge cases beyond the standard ones"""
    
    def test_create_multiple_demographics_same_dimension(self, authenticated_client: TestClient):
        """🧩 Test creating multiple demographics for the same dimension"""
        # Create a dimension
        dimension = self.create_dimension(authenticated_client)
        
        # Create multiple demographics for the same dimension
        demographics = []
        for i in range(3):
            demo_data = {
                "name": f"Age Group {i*10}-{(i+1)*10}",
                "description": f"Age demographic {i}",
                "dimension_id": dimension["id"]
            }
            response = authenticated_client.post(self.endpoints.create, json=demo_data)
            assert response.status_code == status.HTTP_200_OK
            demographics.append(response.json())
        
        # Verify all demographics were created with same dimension
        for demo in demographics:
            assert demo["dimension_id"] == dimension["id"]
        
        # Clean up
        for demo in demographics:
            authenticated_client.delete(self.endpoints.remove(demo["id"]))
    
    def test_demographic_cascade_behavior_on_dimension_deletion(self, authenticated_client: TestClient):
        """🧩 Test behavior when referenced dimension is deleted"""
        # Create dimension and demographic
        dimension = self.create_dimension(authenticated_client)
        demographic_data = {
            "name": "Cascade Test Demographic",
            "dimension_id": dimension["id"]
        }
        demographic = self.create_entity(authenticated_client, demographic_data)
        
        # Delete the dimension
        dim_delete_response = authenticated_client.delete(APIEndpoints.DIMENSIONS.remove(dimension["id"]))
        
        # Depending on cascade settings, this might succeed or fail
        if dim_delete_response.status_code == status.HTTP_200_OK:
            # If dimension deletion succeeded, check demographic status
            demo_get_response = authenticated_client.get(self.endpoints.get(demographic["id"]))
            # Demographic might still exist with null dimension_id or be deleted
            assert demo_get_response.status_code in [
                status.HTTP_200_OK,  # Still exists
                status.HTTP_404_NOT_FOUND  # Cascaded deletion
            ]
        else:
            # If dimension deletion failed due to foreign key constraint
            assert dim_delete_response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_409_CONFLICT
            ]
    
    def test_create_demographic_with_very_long_name(self, authenticated_client: TestClient):
        """🧩 Test creating demographic with very long name"""
        demographic_data = {
            "name": fake.text(max_nb_chars=500),  # Very long name
            "description": fake.text(max_nb_chars=100)
        }

        response = authenticated_client.post(self.endpoints.create, json=demographic_data)

        # Should either succeed or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]
    
    def test_demographic_with_special_characters(self, authenticated_client: TestClient):
        """🧩 Test demographic with special characters and unicode"""
        demographic_data = {
            "name": f"Démographic with émoji 🧪 & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}",
            "description": "Déscription with spëcial characters and unicode: 你好世界"
        }

        response = authenticated_client.post(self.endpoints.create, json=demographic_data)

        # Should handle special characters gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["name"] == demographic_data["name"]
    
    def test_demographic_sorting_and_pagination(self, authenticated_client: TestClient):
        """🧩 Test demographic listing with various sorting and pagination"""
        # Create multiple demographics
        demographics = []
        for i in range(5):
            demo_data = {
                "name": f"Sort Test Demographic {chr(65+i)}",  # A, B, C, D, E
                "description": f"Description {i}"
            }
            response = authenticated_client.post(self.endpoints.create, json=demo_data)
            assert response.status_code == status.HTTP_200_OK
            demographics.append(response.json())
        
        # Test sorting by name ascending
        response = authenticated_client.get(f"{self.endpoints.list}?sort_by=name&sort_order=asc&limit=10")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        
        # Test pagination
        response = authenticated_client.get(f"{self.endpoints.list}?skip=2&limit=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 2
        
        # Clean up
        for demo in demographics:
            authenticated_client.delete(self.endpoints.remove(demo["id"]))


@pytest.mark.integration
@pytest.mark.critical
class TestDemographicDimensionIntegration(DemographicTestMixin, BaseEntityTests):
    """Integration tests for demographic-dimension relationships"""
    
    def test_complete_demographic_dimension_workflow(self, authenticated_client: TestClient):
        """🔗🔥 Test complete workflow: create dimension, create demographics, manage relationships"""
        # Step 1: Create a dimension
        dimension_data = {
            "name": "Age Groups",
            "description": "Demographic dimension for age-based segmentation"
        }
        dimension_response = authenticated_client.post(APIEndpoints.DIMENSIONS.create, json=dimension_data)
        assert dimension_response.status_code == status.HTTP_200_OK
        dimension = dimension_response.json()
        
        # Step 2: Create multiple demographics for this dimension
        age_groups = [
            {"name": "18-25", "description": "Young adults"},
            {"name": "26-35", "description": "Young professionals"},
            {"name": "36-50", "description": "Middle-aged adults"},
            {"name": "51+", "description": "Older adults"}
        ]
        
        created_demographics = []
        for group in age_groups:
            demo_data = {
                "name": f"Age Group {group['name']}",
                "description": group["description"],
                "dimension_id": dimension["id"]
            }
            response = authenticated_client.post(self.endpoints.create, json=demo_data)
            assert response.status_code == status.HTTP_200_OK
            created_demographics.append(response.json())
        
        # Step 3: Verify all demographics are linked to dimension
        for demo in created_demographics:
            assert demo["dimension_id"] == dimension["id"]
            
            # Verify individual retrieval
            get_response = authenticated_client.get(self.endpoints.get(demo["id"]))
            assert get_response.status_code == status.HTTP_200_OK
            assert get_response.json()["dimension_id"] == dimension["id"]
        
        # Step 4: Test updating demographic relationships
        first_demo = created_demographics[0]
        update_data = {
            "description": "Updated: " + first_demo["description"],
            "dimension_id": dimension["id"]  # Keep same dimension
        }
        update_response = authenticated_client.put(self.endpoints.put(first_demo["id"]), json=update_data)
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["dimension_id"] == dimension["id"]
        
        # Step 5: Test removing dimension relationship
        remove_dim_data = {"dimension_id": None}
        remove_response = authenticated_client.put(self.endpoints.put(first_demo["id"]), json=remove_dim_data)
        assert remove_response.status_code == status.HTTP_200_OK
        assert remove_response.json()["dimension_id"] is None
        
        # Step 6: Clean up
        for demo in created_demographics:
            authenticated_client.delete(self.endpoints.remove(demo["id"]))
        authenticated_client.delete(APIEndpoints.DIMENSIONS.remove(dimension["id"]))
    
    def test_demographic_orphaning_scenarios(self, authenticated_client: TestClient):
        """🔗 Test demographics when dimensions are modified or deleted"""
        # Create dimension and demographic
        dimension = self.create_dimension(authenticated_client)
        demo_data = {
            "name": "Orphan Test Demographic",
            "dimension_id": dimension["id"]
        }
        demographic = self.create_entity(authenticated_client, demo_data)
        
        # Test what happens when we try to delete dimension with demographics
        delete_response = authenticated_client.delete(APIEndpoints.DIMENSIONS.remove(dimension["id"]))
        
        if delete_response.status_code == status.HTTP_200_OK:
            # Dimension was deleted (cascade or demographic was orphaned)
            demo_check = authenticated_client.get(self.endpoints.get(demographic["id"]))
            if demo_check.status_code == status.HTTP_200_OK:
                # Demographic still exists, check if dimension_id is null
                assert demo_check.json()["dimension_id"] is None
        else:
            # Dimension deletion was prevented by foreign key constraint
            assert delete_response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_409_CONFLICT
            ]
            # Demographic should still exist and be linked
            demo_check = authenticated_client.get(self.endpoints.get(demographic["id"]))
            assert demo_check.status_code == status.HTTP_200_OK
            assert demo_check.json()["dimension_id"] == dimension["id"]


@pytest.mark.slow
@pytest.mark.integration
class TestDemographicPerformance(DemographicTestMixin, BaseEntityTests):
    """Performance tests for demographic operations"""
    
    def test_bulk_demographic_creation_with_dimensions(self, authenticated_client: TestClient):
        """🐌 Test creating many demographics with dimension relationships"""
        import time
        
        # Create a few dimensions first
        dimensions = []
        for i in range(3):
            dim_data = {
                "name": f"Performance Dimension {i}",
                "description": f"Performance test dimension {i}"
            }
            response = authenticated_client.post(APIEndpoints.DIMENSIONS.create, json=dim_data)
            assert response.status_code == status.HTTP_200_OK
            dimensions.append(response.json())
        
        start_time = time.time()
        
        # Create 20 demographics across the dimensions
        created_demographics = []
        for i in range(20):
            dimension = dimensions[i % len(dimensions)]  # Rotate through dimensions
            demo_data = {
                "name": f"Performance Test Demographic {i}",
                "description": f"Performance test demographic {i}",
                "dimension_id": dimension["id"]
            }
            response = authenticated_client.post(self.endpoints.create, json=demo_data)
            assert response.status_code == status.HTTP_200_OK
            created_demographics.append(response.json())
        
        duration = time.time() - start_time
        
        # Should complete within reasonable time (20 seconds for 20 creates)
        assert duration < 20.0
        assert len(created_demographics) == 20
        
        # Clean up
        for demo in created_demographics:
            authenticated_client.delete(self.endpoints.remove(demo["id"]))
        for dim in dimensions:
            authenticated_client.delete(APIEndpoints.DIMENSIONS.remove(dim["id"]))


class TestDemographicHealthChecks(DemographicTestMixin, BaseEntityTests):
    """Health checks for demographic endpoints"""
    
    def test_demographic_endpoints_accessibility(self, authenticated_client: TestClient):
        """✅ Test that demographic endpoints are accessible"""
        # Test list endpoint
        response = authenticated_client.get(self.endpoints.list)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_demographic_crud_cycle_health(self, authenticated_client: TestClient):
        """✅ Test complete demographic CRUD cycle"""
        # Create
        demographic_data = self.get_sample_data()
        create_response = authenticated_client.post(self.endpoints.create, json=demographic_data)
        assert create_response.status_code == status.HTTP_200_OK
        created = create_response.json()
        
        # Read
        read_response = authenticated_client.get(self.endpoints.get(created["id"]))
        assert read_response.status_code == status.HTTP_200_OK
        
        # Update
        update_data = {"name": "Updated Health Check Demographic"}
        update_response = authenticated_client.put(self.endpoints.put(created["id"]), json=update_data)
        assert update_response.status_code == status.HTTP_200_OK
        
        # Delete
        delete_response = authenticated_client.delete(self.endpoints.remove(created["id"]))
        assert delete_response.status_code == status.HTTP_200_OK
        
        # Verify deletion
        verify_response = authenticated_client.get(self.endpoints.get(created["id"]))
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_demographic_dimension_relationship_health(self, authenticated_client: TestClient):
        """✅ Test demographic-dimension relationship health"""
        # Create dimension
        dimension = self.create_dimension(authenticated_client)
        
        # Create demographic with dimension
        demo_data = {
            "name": "Relationship Health Test",
            "dimension_id": dimension["id"]
        }
        demo_response = authenticated_client.post(self.endpoints.create, json=demo_data)
        assert demo_response.status_code == status.HTTP_200_OK
        demographic = demo_response.json()
        
        # Verify relationship
        assert demographic["dimension_id"] == dimension["id"]
        
        # Clean up
        authenticated_client.delete(self.endpoints.remove(demographic["id"]))
        authenticated_client.delete(APIEndpoints.DIMENSIONS.remove(dimension["id"]))
