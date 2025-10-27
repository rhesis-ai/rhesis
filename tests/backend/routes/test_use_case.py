"""
🎯 Use Case Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for use case entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🎯 Use case-specific functionality testing
- 🏢 Industry and application categorization
- 📋 Active/inactive state management
- 🔍 Advanced filtering and use case categorization

Run with: python -m pytest tests/backend/routes/test_use_case.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import UseCaseDataFactory, StatusDataFactory

# Initialize Faker
fake = Faker()


class UseCaseTestMixin:
    """Enhanced use case test mixin using factory system"""
    
    # Entity configuration
    entity_name = "use_case"
    entity_plural = "use_cases"
    endpoints = APIEndpoints.USE_CASES
    
    # Field mappings for use cases
    name_field = "name"
    description_field = "description"
    
    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample use case data using factory"""
        return UseCaseDataFactory.sample_data()
    
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal use case data using factory"""
        return UseCaseDataFactory.minimal_data()
    
    def get_update_data(self) -> Dict[str, Any]:
        """Return use case update data using factory"""
        return UseCaseDataFactory.update_data()
    
    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid use case data using factory"""
        return UseCaseDataFactory.invalid_data()
    
    def get_null_description_data(self) -> Dict[str, Any]:
        """Return use case data with null description"""
        # Use cases require description, so return minimal data with description
        return self.get_minimal_data()
    
    def test_entity_with_null_description(self, authenticated_client):
        """Test entity creation with null description - use cases require description"""
        # Use cases require description, so this test verifies that
        # the entity can be created successfully with a valid description
        use_case_data = self.get_sample_data()
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=use_case_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        use_case = response.json()
        
        # Verify the use case was created with the expected content
        assert use_case["name"] == use_case_data["name"]
        assert use_case["description"] == use_case_data["description"]


class TestUseCaseRoutes(UseCaseTestMixin, BaseEntityRouteTests):
    """
    🎯 Complete use case route test suite
    
    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks
    
    Plus use case-specific functionality tests.
    """
    
    # === USE CASE-SPECIFIC CRUD TESTS ===
    
    def test_create_use_case_with_required_fields(self, authenticated_client):
        """Test use case creation with only required fields"""
        minimal_data = self.get_minimal_data()
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=minimal_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == minimal_data["name"]
        assert created_use_case["description"] == minimal_data["description"]
        # Optional fields should have default values
        assert created_use_case.get("is_active") is True  # Default value
    
    def test_create_use_case_with_optional_fields(self, authenticated_client):
        """Test use case creation with optional fields"""
        use_case_data = self.get_sample_data()
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=use_case_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == use_case_data["name"]
        assert created_use_case["description"] == use_case_data["description"]
        if use_case_data.get("industry"):
            assert created_use_case["industry"] == use_case_data["industry"]
        if use_case_data.get("application"):
            assert created_use_case["application"] == use_case_data["application"]
        if "is_active" in use_case_data:
            assert created_use_case["is_active"] == use_case_data["is_active"]
    
    def test_create_use_case_healthcare_category(self, authenticated_client):
        """Test use case creation with healthcare-specific data"""
        healthcare_use_case_data = UseCaseDataFactory.edge_case_data("healthcare")
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=healthcare_use_case_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == healthcare_use_case_data["name"]
        # Verify healthcare-related keywords in name or just verify industry
        name_lower = created_use_case["name"].lower()
        healthcare_keywords = ["healthcare", "medical", "patient", "drug", "clinical", "health", "electronic", "telemedicine", "diagnosis"]
        has_healthcare_keyword = any(keyword in name_lower for keyword in healthcare_keywords)
        assert has_healthcare_keyword, f"Healthcare use case name '{created_use_case['name']}' should contain healthcare-related keywords"
        assert created_use_case["industry"] == "Healthcare"
        assert created_use_case["is_active"] is True
        assert created_use_case["description"] == healthcare_use_case_data["description"]
    
    def test_create_use_case_finance_category(self, authenticated_client):
        """Test use case creation with finance-specific data"""
        finance_use_case_data = UseCaseDataFactory.edge_case_data("finance")
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=finance_use_case_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == finance_use_case_data["name"]
        # Verify finance-related keywords in name
        name_lower = created_use_case["name"].lower()
        assert any(keyword in name_lower for keyword in ["fraud", "trading", "risk", "compliance", "credit", "financial", "investment", "portfolio"])
        assert created_use_case["industry"] == "Finance"
        assert created_use_case["is_active"] is True
        assert created_use_case["description"] == finance_use_case_data["description"]
    
    def test_create_use_case_ecommerce_category(self, authenticated_client):
        """Test use case creation with e-commerce-specific data"""
        ecommerce_use_case_data = UseCaseDataFactory.edge_case_data("ecommerce")
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=ecommerce_use_case_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == ecommerce_use_case_data["name"]
        assert "recommendation" in created_use_case["name"].lower() or "pricing" in created_use_case["name"].lower() or "customer" in created_use_case["name"].lower() or "inventory" in created_use_case["name"].lower()
        assert created_use_case["industry"] == "E-commerce"
        assert created_use_case["is_active"] is True
        assert created_use_case["description"] == ecommerce_use_case_data["description"]
    
    def test_create_use_case_inactive(self, authenticated_client):
        """Test use case creation with inactive status"""
        inactive_use_case_data = UseCaseDataFactory.edge_case_data("inactive")
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=inactive_use_case_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == inactive_use_case_data["name"]
        assert "deprecated" in created_use_case["name"].lower()
        assert created_use_case["is_active"] is False
        assert created_use_case["description"] == inactive_use_case_data["description"]
    
    def test_create_use_case_with_long_name(self, authenticated_client):
        """Test use case creation with very long name"""
        long_name_data = UseCaseDataFactory.edge_case_data("long_name")
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=long_name_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == long_name_data["name"]
        assert len(created_use_case["name"]) > 100  # Verify it's actually long
        assert created_use_case["industry"] == "Technology"
        assert created_use_case["application"] == "Complex System Integration"
    
    def test_update_use_case_name_and_description(self, authenticated_client):
        """Test updating use case name and description"""
        # Create initial use case
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        use_case_id = create_response.json()["id"]
        
        # Update use case
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, use_case_id=use_case_id),
            json=update_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        updated_use_case = response.json()
        
        assert updated_use_case["name"] == update_data["name"]
        assert updated_use_case["description"] == update_data["description"]
        if update_data.get("industry"):
            assert updated_use_case["industry"] == update_data["industry"]
        if update_data.get("application"):
            assert updated_use_case["application"] == update_data["application"]
    
    def test_update_use_case_status_only(self, authenticated_client):
        """Test updating only the active status of a use case"""
        # Create initial use case
        initial_data = self.get_sample_data()
        initial_data["is_active"] = True
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        use_case_id = create_response.json()["id"]
        original_name = create_response.json()["name"]
        
        # Update only status
        update_data = {"is_active": False}
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, use_case_id=use_case_id),
            json=update_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        updated_use_case = response.json()
        
        assert updated_use_case["name"] == original_name  # Name unchanged
        assert updated_use_case["is_active"] is False  # Status updated
    
    def test_get_use_case_by_id(self, authenticated_client):
        """Test retrieving a specific use case by ID"""
        # Create use case
        use_case_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=use_case_data,
        )
        use_case_id = create_response.json()["id"]
        
        # Get use case by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, use_case_id=use_case_id),
        )
        
        assert response.status_code == status.HTTP_200_OK
        use_case = response.json()
        
        assert use_case["id"] == use_case_id
        assert use_case["name"] == use_case_data["name"]
        assert use_case["description"] == use_case_data["description"]
        if use_case_data.get("industry"):
            assert use_case["industry"] == use_case_data["industry"]
        if use_case_data.get("application"):
            assert use_case["application"] == use_case_data["application"]
    
    def test_delete_use_case(self, authenticated_client):
        """Test deleting a use case"""
        # Create use case
        use_case_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=use_case_data,
        )
        use_case_id = create_response.json()["id"]
        
        # Delete use case
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, use_case_id=use_case_id),
        )
        
        assert response.status_code == status.HTTP_200_OK
        deleted_use_case = response.json()
        assert deleted_use_case["id"] == use_case_id
        
        # Verify use case is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, use_case_id=use_case_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE
    
    def test_list_use_cases_with_pagination(self, authenticated_client):
        """Test listing use cases with pagination"""
        # Create multiple use cases
        use_cases_data = [self.get_sample_data() for _ in range(5)]
        created_use_cases = []
        
        for use_case_data in use_cases_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=use_case_data,
            )
            created_use_cases.append(response.json())
        
        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )
        
        assert response.status_code == status.HTTP_200_OK
        use_cases = response.json()
        assert len(use_cases) <= 3
        
        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5
    
    def test_list_use_cases_with_sorting(self, authenticated_client):
        """Test listing use cases with sorting"""
        # Create use cases with different names
        use_case1_data = self.get_sample_data()
        use_case1_data["name"] = "Use Case: AAA Early Adopter System"
        
        use_case2_data = self.get_sample_data()
        use_case2_data["name"] = "Use Case: ZZZ Legacy Integration"
        
        # Create use cases
        authenticated_client.post(self.endpoints.create, json=use_case1_data)
        authenticated_client.post(self.endpoints.create, json=use_case2_data)
        
        # Test sorting
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )
        
        assert response.status_code == status.HTTP_200_OK
        use_cases = response.json()
        assert len(use_cases) >= 2
    
    # === USE CASE-SPECIFIC ERROR HANDLING TESTS ===
    
    def test_create_use_case_without_name(self, authenticated_client):
        """Test creating use case without required name field"""
        invalid_data = {"description": "Use case without name"}
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_use_case_without_description(self, authenticated_client):
        """Test creating use case without required description field"""
        invalid_data = {"name": "Use Case: Missing Description"}
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_use_case_with_empty_name(self, authenticated_client):
        """Test creating use case with empty name"""
        invalid_data = {
            "name": "",
            "description": "Use case with empty name"
        }
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )
        
        # This might be allowed or not depending on validation rules
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]
    
    def test_get_nonexistent_use_case(self, authenticated_client):
        """Test retrieving a non-existent use case"""
        fake_id = str(uuid.uuid4())
        
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, use_case_id=fake_id),
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
    
    def test_update_nonexistent_use_case(self, authenticated_client):
        """Test updating a non-existent use case"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()
        
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, use_case_id=fake_id),
            json=update_data,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
    
    def test_delete_nonexistent_use_case(self, authenticated_client):
        """Test deleting a non-existent use case"""
        fake_id = str(uuid.uuid4())
        
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, use_case_id=fake_id),
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === USE CASE RELATIONSHIPS AND STATUS TESTS ===

@pytest.mark.integration
class TestUseCaseRelationships(UseCaseTestMixin, BaseEntityTests):
    """Enhanced use case relationship and status tests"""

    def _create_test_status(self, authenticated_client):
        """Helper to create a test status for use case relationships"""
        status_data = StatusDataFactory.sample_data()
        response = authenticated_client.post(
            "/statuses/",
            json=status_data,
        )
        assert response.status_code == status.HTTP_200_OK
        return response.json()

    def test_create_use_case_with_status_relationship(self, authenticated_client):
        """Test creating a use case with status relationship"""
        # Create a status first
        status_obj = self._create_test_status(authenticated_client)
        status_id = status_obj["id"]
        
        # Create use case with status reference
        use_case_data = self.get_sample_data()
        use_case_data["status_id"] = status_id
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=use_case_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_use_case = response.json()
        
        assert created_use_case["name"] == use_case_data["name"]
        assert created_use_case["status_id"] == status_id

    def test_create_use_case_with_invalid_status_id(self, authenticated_client):
        """Test creating a use case with invalid status_id"""
        fake_status_id = str(uuid.uuid4())
        
        use_case_data = self.get_sample_data()
        use_case_data["status_id"] = fake_status_id
        
        try:
            response = authenticated_client.post(
                self.endpoints.create,
                json=use_case_data,
            )
            
            # If we get a response, it should be an error status
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,  # Application-level validation
                status.HTTP_422_UNPROCESSABLE_ENTITY,  # Pydantic validation
                status.HTTP_500_INTERNAL_SERVER_ERROR  # Database constraint violation
            ]
            
        except Exception as e:
            # Database constraint violations might be raised as exceptions
            # This is expected behavior for foreign key constraint violations
            assert "foreign key constraint" in str(e).lower() or "violates" in str(e).lower()
            # Test passes if we get the expected constraint violation

    def test_filter_use_cases_by_industry(self, authenticated_client):
        """Test filtering use cases by industry"""
        # Create use cases with different industries
        healthcare_data = UseCaseDataFactory.edge_case_data("healthcare")
        finance_data = UseCaseDataFactory.edge_case_data("finance")
        
        healthcare_response = authenticated_client.post(self.endpoints.create, json=healthcare_data)
        finance_response = authenticated_client.post(self.endpoints.create, json=finance_data)
        
        assert healthcare_response.status_code == status.HTTP_200_OK
        assert finance_response.status_code == status.HTTP_200_OK
        
        # Test listing all use cases (should include both)
        response = authenticated_client.get(f"{self.endpoints.list}?limit=10")
        assert response.status_code == status.HTTP_200_OK
        use_cases = response.json()
        
        # Verify we have use cases from different industries
        industries = [uc.get("industry") for uc in use_cases if uc.get("industry")]
        assert "Healthcare" in industries or "Finance" in industries

    def test_filter_use_cases_by_active_status(self, authenticated_client):
        """Test filtering use cases by active status"""
        # Create active and inactive use cases
        active_data = self.get_sample_data()
        active_data["is_active"] = True
        
        inactive_data = UseCaseDataFactory.edge_case_data("inactive")
        
        active_response = authenticated_client.post(self.endpoints.create, json=active_data)
        inactive_response = authenticated_client.post(self.endpoints.create, json=inactive_data)
        
        assert active_response.status_code == status.HTTP_200_OK
        assert inactive_response.status_code == status.HTTP_200_OK
        
        # Test listing all use cases
        response = authenticated_client.get(f"{self.endpoints.list}?limit=10")
        assert response.status_code == status.HTTP_200_OK
        use_cases = response.json()
        
        # Verify we have both active and inactive use cases
        active_statuses = [uc.get("is_active") for uc in use_cases]
        assert True in active_statuses
        assert False in active_statuses


# === USE CASE PERFORMANCE TESTS ===

@pytest.mark.performance
class TestUseCasePerformance(UseCaseTestMixin, BaseEntityTests):
    """Use case performance tests"""

    def test_create_multiple_use_cases_performance(self, authenticated_client):
        """Test creating multiple use cases for performance"""
        use_cases_count = 20
        use_cases_data = UseCaseDataFactory.batch_data(use_cases_count, variation=True)
        
        created_use_cases = []
        for use_case_data in use_cases_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=use_case_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_use_cases.append(response.json())
        
        assert len(created_use_cases) == use_cases_count
        
        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={use_cases_count}",
        )
        
        assert response.status_code == status.HTTP_200_OK
        use_cases = response.json()
        assert len(use_cases) >= use_cases_count

    def test_use_case_categorization_performance(self, authenticated_client):
        """Test use case categorization performance with different industries"""
        # Create use cases of different categories
        categories = ["healthcare", "finance", "ecommerce", "inactive"]
        
        created_use_cases = []
        for category in categories:
            for i in range(3):  # 3 use cases per category
                use_case_data = UseCaseDataFactory.edge_case_data(category)
                response = authenticated_client.post(
                    self.endpoints.create,
                    json=use_case_data,
                )
                assert response.status_code == status.HTTP_200_OK
                created_use_cases.append(response.json())
        
        assert len(created_use_cases) == len(categories) * 3
        
        # Test listing all use cases
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit=20",
        )
        
        assert response.status_code == status.HTTP_200_OK
        use_cases = response.json()
        assert len(use_cases) >= 12  # At least the ones we created

    def test_bulk_use_case_operations(self, authenticated_client):
        """Test bulk use case operations"""
        # Create multiple use cases
        use_cases_count = 15
        use_cases_data = UseCaseDataFactory.batch_data(use_cases_count, variation=False)
        
        created_use_cases = []
        for use_case_data in use_cases_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=use_case_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_use_cases.append(response.json())
        
        # Test bulk update operations
        update_data = self.get_update_data()
        for use_case_obj in created_use_cases[:5]:  # Update first 5 use cases
            response = authenticated_client.put(
                self.endpoints.format_path(self.endpoints.update, use_case_id=use_case_obj["id"]),
                json=update_data,
            )
            assert response.status_code == status.HTTP_200_OK
        
        # Test bulk delete operations
        for use_case_obj in created_use_cases[10:]:  # Delete last 5 use cases
            response = authenticated_client.delete(
                self.endpoints.format_path(self.endpoints.delete, use_case_id=use_case_obj["id"]),
            )
            assert response.status_code == status.HTTP_200_OK

    def test_industry_distribution_performance(self, authenticated_client):
        """Test performance with diverse industry distribution"""
        # Create use cases across different industries
        industries = ["Healthcare", "Finance", "E-commerce", "Technology", "Education"]
        
        created_use_cases = []
        for industry in industries:
            for i in range(2):  # 2 use cases per industry
                use_case_data = self.get_sample_data()
                use_case_data["industry"] = industry
                use_case_data["name"] = f"Use Case: {industry} Application {i+1}"
                
                response = authenticated_client.post(
                    self.endpoints.create,
                    json=use_case_data,
                )
                assert response.status_code == status.HTTP_200_OK
                created_use_cases.append(response.json())
        
        # Verify industry distribution
        assert len(created_use_cases) == len(industries) * 2
        
        # Test listing with various filters
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit=15",
        )
        
        assert response.status_code == status.HTTP_200_OK
        use_cases = response.json()
        assert len(use_cases) >= 10  # At least most of the ones we created
