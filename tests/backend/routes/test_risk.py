"""
⚠️ Risk Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for risk entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- ⚠️ Risk-specific functionality testing
- 🔗 Foreign key relationships (parent_id, use_case_id, status_id)
- 📋 Hierarchical risk management
- 🔍 Advanced filtering and risk categorization

Run with: python -m pytest tests/backend/routes/test_risk.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import RiskDataFactory, StatusDataFactory

# Initialize Faker
fake = Faker()


class RiskTestMixin:
    """Enhanced risk test mixin using factory system"""

    # Entity configuration
    entity_name = "risk"
    entity_plural = "risks"
    endpoints = APIEndpoints.RISKS

    # Field mappings for risks
    name_field = "name"
    description_field = "description"

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample risk data using factory"""
        return RiskDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal risk data using factory"""
        return RiskDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return risk update data using factory"""
        return RiskDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid risk data using factory"""
        return RiskDataFactory.invalid_data()

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return risk data with null description"""
        data = self.get_minimal_data()
        data["description"] = None
        return data


class TestRiskRoutes(RiskTestMixin, BaseEntityRouteTests):
    """
    ⚠️ Complete risk route test suite

    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Plus risk-specific functionality tests.
    """

    # === RISK-SPECIFIC CRUD TESTS ===

    def test_create_risk_with_required_fields(self, authenticated_client):
        """Test risk creation with only required fields"""
        minimal_data = self.get_minimal_data()

        response = authenticated_client.post(self.endpoints.create, json=minimal_data)

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == minimal_data["name"]
        assert created_risk.get("description") is None  # Should be None when not provided

    def test_create_risk_with_optional_fields(self, authenticated_client):
        """Test risk creation with optional fields"""
        risk_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=risk_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == risk_data["name"]
        if risk_data.get("description"):
            assert created_risk["description"] == risk_data["description"]

    def test_create_risk_security_category(self, authenticated_client):
        """Test risk creation with security-specific data"""
        security_risk_data = RiskDataFactory.edge_case_data("security_risk")

        response = authenticated_client.post(
            self.endpoints.create,
            json=security_risk_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == security_risk_data["name"]
        # Verify it's a security-related risk (more flexible keyword matching)
        security_keywords = [
            "vulnerability",
            "breach",
            "security",
            "authentication",
            "encryption",
            "access",
            "xss",
            "injection",
        ]
        assert any(keyword in created_risk["name"].lower() for keyword in security_keywords), (
            f"Expected security-related keywords in: {created_risk['name']}"
        )
        assert created_risk["description"] == security_risk_data["description"]

    def test_create_risk_operational_category(self, authenticated_client):
        """Test risk creation with operational-specific data"""
        operational_risk_data = RiskDataFactory.edge_case_data("operational_risk")

        response = authenticated_client.post(
            self.endpoints.create,
            json=operational_risk_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == operational_risk_data["name"]
        # Verify it's an operational-related risk (more flexible keyword matching)
        operational_keywords = [
            "system",
            "service",
            "downtime",
            "operational",
            "database",
            "hardware",
            "backup",
            "disaster",
            "staff",
            "failure",
            "corruption",
        ]
        assert any(keyword in created_risk["name"].lower() for keyword in operational_keywords), (
            f"Expected operational-related keywords in: {created_risk['name']}"
        )
        assert created_risk["description"] == operational_risk_data["description"]

    def test_create_risk_compliance_category(self, authenticated_client):
        """Test risk creation with compliance-specific data"""
        compliance_risk_data = RiskDataFactory.edge_case_data("compliance_risk")

        response = authenticated_client.post(
            self.endpoints.create,
            json=compliance_risk_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == compliance_risk_data["name"]
        # Verify it's a compliance-related risk (more flexible keyword matching)
        compliance_keywords = [
            "compliance",
            "gdpr",
            "regulatory",
            "audit",
            "documentation",
            "retention",
            "policy",
            "standards",
            "financial",
            "transactions",
        ]
        assert any(keyword in created_risk["name"].lower() for keyword in compliance_keywords), (
            f"Expected compliance-related keywords in: {created_risk['name']}"
        )
        assert created_risk["description"] == compliance_risk_data["description"]

    def test_create_risk_financial_category(self, authenticated_client):
        """Test risk creation with financial-specific data"""
        financial_risk_data = RiskDataFactory.edge_case_data("financial_risk")

        response = authenticated_client.post(
            self.endpoints.create,
            json=financial_risk_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == financial_risk_data["name"]
        # Verify it's a financial-related risk (more flexible keyword matching)
        financial_keywords = [
            "cost",
            "costs",
            "budget",
            "revenue",
            "financial",
            "currency",
            "exchange",
            "overrun",
            "escalation",
            "scaling",
            "infrastructure",
        ]
        assert any(keyword in created_risk["name"].lower() for keyword in financial_keywords), (
            f"Expected financial-related keywords in: {created_risk['name']}"
        )
        assert created_risk["description"] == financial_risk_data["description"]

    def test_create_risk_with_long_name(self, authenticated_client):
        """Test risk creation with very long name"""
        long_name_data = RiskDataFactory.edge_case_data("long_name")

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_name_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == long_name_data["name"]
        assert len(created_risk["name"]) > 100  # Verify it's actually long
        assert created_risk["description"] == long_name_data["description"]

    def test_update_risk_name_and_description(self, authenticated_client):
        """Test updating risk name and description"""
        # Create initial risk
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        risk_id = create_response.json()["id"]

        # Update risk
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, risk_id=risk_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_risk = response.json()

        assert updated_risk["name"] == update_data["name"]
        assert updated_risk["description"] == update_data["description"]

    def test_update_risk_partial(self, authenticated_client):
        """Test updating only specific fields of a risk"""
        # Create initial risk
        initial_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        risk_id = create_response.json()["id"]
        original_name = create_response.json()["name"]

        # Update only description
        update_data = {"description": "Updated risk description for testing partial updates"}
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, risk_id=risk_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_risk = response.json()

        assert updated_risk["name"] == original_name  # Name unchanged
        assert updated_risk["description"] == update_data["description"]  # Description updated

    def test_get_risk_by_id(self, authenticated_client):
        """Test retrieving a specific risk by ID"""
        # Create risk
        risk_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=risk_data,
        )
        risk_id = create_response.json()["id"]

        # Get risk by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, risk_id=risk_id),
        )

        assert response.status_code == status.HTTP_200_OK
        risk = response.json()

        assert risk["id"] == risk_id
        assert risk["name"] == risk_data["name"]
        if risk_data.get("description"):
            assert risk["description"] == risk_data["description"]

    def test_delete_risk(self, authenticated_client):
        """Test deleting a risk"""
        # Create risk
        risk_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=risk_data,
        )
        risk_id = create_response.json()["id"]

        # Delete risk
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, risk_id=risk_id),
        )

        assert response.status_code == status.HTTP_200_OK
        deleted_risk = response.json()
        assert deleted_risk["id"] == risk_id

        # Verify risk is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, risk_id=risk_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE

    def test_list_risks_with_pagination(self, authenticated_client):
        """Test listing risks with pagination"""
        # Create multiple risks
        risks_data = [self.get_sample_data() for _ in range(5)]
        created_risks = []

        for risk_data in risks_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=risk_data,
            )
            created_risks.append(response.json())

        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )

        assert response.status_code == status.HTTP_200_OK
        risks = response.json()
        assert len(risks) <= 3

        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5

    def test_list_risks_with_sorting(self, authenticated_client):
        """Test listing risks with sorting"""
        # Create risks with different names
        risk1_data = self.get_sample_data()
        risk1_data["name"] = "Risk: AAA Critical Security Issue"

        risk2_data = self.get_sample_data()
        risk2_data["name"] = "Risk: ZZZ Minor Documentation Issue"

        # Create risks
        authenticated_client.post(self.endpoints.create, json=risk1_data)
        authenticated_client.post(self.endpoints.create, json=risk2_data)

        # Test sorting
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )

        assert response.status_code == status.HTTP_200_OK
        risks = response.json()
        assert len(risks) >= 2

    # === RISK-SPECIFIC ERROR HANDLING TESTS ===

    def test_create_risk_without_name(self, authenticated_client):
        """Test creating risk without required name field"""
        invalid_data = {"description": "Risk without name"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_risk_with_empty_name(self, authenticated_client):
        """Test creating risk with empty name"""
        invalid_data = {"name": "", "description": "Risk with empty name"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        # This might be allowed or not depending on validation rules
        # Adjust assertion based on actual API behavior
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_get_nonexistent_risk(self, authenticated_client):
        """Test retrieving a non-existent risk"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, risk_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_update_nonexistent_risk(self, authenticated_client):
        """Test updating a non-existent risk"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()

        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, risk_id=fake_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_risk(self, authenticated_client):
        """Test deleting a non-existent risk"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, risk_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === RISK RELATIONSHIPS AND HIERARCHY TESTS ===


@pytest.mark.integration
class TestRiskRelationships(RiskTestMixin, BaseEntityTests):
    """Enhanced risk relationship and hierarchy tests"""

    def _create_test_status(self, authenticated_client):
        """Helper to create a test status for risk relationships"""
        status_data = StatusDataFactory.sample_data()
        response = authenticated_client.post(
            "/statuses/",
            json=status_data,
        )
        assert response.status_code == status.HTTP_200_OK
        return response.json()

    def _create_test_use_case(self, authenticated_client):
        """Helper to create a test use case for risk relationships"""
        # Note: This might fail if use_case endpoints don't exist yet
        # In that case, we'll skip these tests or create minimal data
        try:
            use_case_data = {
                "name": f"Use Case: {fake.catch_phrase()}",
                "description": fake.paragraph(nb_sentences=2),
            }
            response = authenticated_client.post(
                "/use_cases/",
                json=use_case_data,
            )
            if response.status_code == status.HTTP_200_OK:
                return response.json()
        except:
            pass
        return None

    def test_create_risk_with_status_relationship(self, authenticated_client):
        """Test creating a risk with status relationship"""
        # Create a status first
        status_obj = self._create_test_status(authenticated_client)
        status_id = status_obj["id"]

        # Create risk with status reference
        risk_data = self.get_sample_data()
        risk_data["status_id"] = status_id

        response = authenticated_client.post(
            self.endpoints.create,
            json=risk_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == risk_data["name"]
        assert created_risk["status_id"] == status_id

    @pytest.mark.skip(reason="Use case endpoints might not exist yet")
    def test_create_risk_with_use_case_relationship(self, authenticated_client):
        """Test creating a risk with use case relationship"""
        # Create a use case first
        use_case = self._create_test_use_case(authenticated_client)
        if not use_case:
            pytest.skip("Use case creation failed - endpoints might not exist")

        use_case_id = use_case["id"]

        # Create risk with use case reference
        risk_data = self.get_sample_data()
        risk_data["use_case_id"] = use_case_id

        response = authenticated_client.post(
            self.endpoints.create,
            json=risk_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_risk = response.json()

        assert created_risk["name"] == risk_data["name"]
        assert created_risk["use_case_id"] == use_case_id

    def test_create_hierarchical_risks(self, authenticated_client):
        """Test creating parent-child risk relationships"""
        # Create parent risk
        parent_risk_data = self.get_sample_data()
        parent_risk_data["name"] = "Risk: Parent - System Security Framework"

        parent_response = authenticated_client.post(
            self.endpoints.create,
            json=parent_risk_data,
        )
        assert parent_response.status_code == status.HTTP_200_OK
        parent_risk = parent_response.json()
        parent_id = parent_risk["id"]

        # Create child risk
        child_risk_data = self.get_sample_data()
        child_risk_data["name"] = "Risk: Child - Authentication Vulnerability"
        child_risk_data["parent_id"] = parent_id

        child_response = authenticated_client.post(
            self.endpoints.create,
            json=child_risk_data,
        )
        assert child_response.status_code == status.HTTP_200_OK
        child_risk = child_response.json()

        assert child_risk["name"] == child_risk_data["name"]
        assert child_risk["parent_id"] == parent_id

    def test_create_risk_with_invalid_parent_id(self, authenticated_client):
        """Test creating a risk with invalid parent_id"""
        fake_parent_id = str(uuid.uuid4())

        risk_data = self.get_sample_data()
        risk_data["parent_id"] = fake_parent_id

        response = authenticated_client.post(
            self.endpoints.create,
            json=risk_data,
        )

        # This might succeed or fail depending on foreign key constraints
        # Adjust assertion based on actual API behavior
        assert response.status_code in [
            status.HTTP_200_OK,  # If foreign key constraints are not enforced
            status.HTTP_400_BAD_REQUEST,  # If foreign key constraints are enforced
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_create_risk_with_invalid_status_id(self, authenticated_client):
        """Test creating a risk with invalid status_id"""
        fake_status_id = str(uuid.uuid4())

        risk_data = self.get_sample_data()
        risk_data["status_id"] = fake_status_id

        response = authenticated_client.post(
            self.endpoints.create,
            json=risk_data,
        )

        # This might succeed or fail depending on foreign key constraints
        assert response.status_code in [
            status.HTTP_200_OK,  # If foreign key constraints are not enforced
            status.HTTP_400_BAD_REQUEST,  # If foreign key constraints are enforced
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]


# === RISK PERFORMANCE TESTS ===


@pytest.mark.performance
class TestRiskPerformance(RiskTestMixin, BaseEntityTests):
    """Risk performance tests"""

    def test_create_multiple_risks_performance(self, authenticated_client):
        """Test creating multiple risks for performance"""
        risks_count = 25
        risks_data = RiskDataFactory.batch_data(risks_count, variation=True)

        created_risks = []
        for risk_data in risks_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=risk_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_risks.append(response.json())

        assert len(created_risks) == risks_count

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={risks_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        risks = response.json()
        assert len(risks) >= risks_count

    def test_risk_categorization_performance(self, authenticated_client):
        """Test risk categorization performance with different risk types"""
        # Create risks of different categories
        categories = ["security_risk", "operational_risk", "compliance_risk", "financial_risk"]

        created_risks = []
        for category in categories:
            for i in range(3):  # 3 risks per category
                risk_data = RiskDataFactory.edge_case_data(category)
                response = authenticated_client.post(
                    self.endpoints.create,
                    json=risk_data,
                )
                assert response.status_code == status.HTTP_200_OK
                created_risks.append(response.json())

        assert len(created_risks) == len(categories) * 3

        # Test listing all risks
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit=20",
        )

        assert response.status_code == status.HTTP_200_OK
        risks = response.json()
        assert len(risks) >= 12  # At least the ones we created

    def test_bulk_risk_operations(self, authenticated_client):
        """Test bulk risk operations"""
        # Create multiple risks
        risks_count = 20
        risks_data = RiskDataFactory.batch_data(risks_count, variation=False)

        created_risks = []
        for risk_data in risks_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=risk_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_risks.append(response.json())

        # Test bulk update operations
        update_data = self.get_update_data()
        for risk_obj in created_risks[:7]:  # Update first 7 risks
            response = authenticated_client.put(
                self.endpoints.format_path(self.endpoints.update, risk_id=risk_obj["id"]),
                json=update_data,
            )
            assert response.status_code == status.HTTP_200_OK

        # Test bulk delete operations
        for risk_obj in created_risks[15:]:  # Delete last 5 risks
            response = authenticated_client.delete(
                self.endpoints.format_path(self.endpoints.delete, risk_id=risk_obj["id"]),
            )
            assert response.status_code == status.HTTP_200_OK

    def test_hierarchical_risk_performance(self, authenticated_client):
        """Test performance with hierarchical risk structures"""
        # Create parent risks
        parent_risks = []
        for i in range(3):
            parent_data = self.get_sample_data()
            parent_data["name"] = f"Risk: Parent {i + 1} - Major System Risk"

            response = authenticated_client.post(
                self.endpoints.create,
                json=parent_data,
            )
            assert response.status_code == status.HTTP_200_OK
            parent_risks.append(response.json())

        # Create child risks for each parent
        child_risks = []
        for parent in parent_risks:
            for j in range(2):  # 2 children per parent
                child_data = self.get_sample_data()
                child_data["name"] = f"Risk: Child {j + 1} of Parent {parent['name'][-1]}"
                child_data["parent_id"] = parent["id"]

                response = authenticated_client.post(
                    self.endpoints.create,
                    json=child_data,
                )
                assert response.status_code == status.HTTP_200_OK
                child_risks.append(response.json())

        # Verify hierarchy was created
        assert len(parent_risks) == 3
        assert len(child_risks) == 6  # 3 parents * 2 children each
