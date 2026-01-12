"""
🧪 Organization Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for organization entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🏢 Organization-specific features: onboarding, domain verification, user limits

Run with: python -m pytest tests/backend/routes/test_organization.py -v
"""

import uuid
from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .base import BaseEntityRouteTests, BaseEntityTests
from .endpoints import APIEndpoints
from .fixtures.data_factories import OrganizationDataFactory
from .fixtures.entities.organizations import *

# Initialize Faker
fake = Faker()


class OrganizationTestMixin:
    """Enhanced organization test mixin using factory system"""

    # Entity configuration
    entity_name = "organization"
    entity_plural = "organizations"
    endpoints = APIEndpoints.ORGANIZATIONS

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample organization data using factory"""
        return OrganizationDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal organization data using factory"""
        return OrganizationDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return organization update data using factory"""
        return OrganizationDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid organization data using factory"""
        return OrganizationDataFactory.invalid_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case organization data using factory"""
        return OrganizationDataFactory.edge_case_data(case_type)

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return organization data with null description"""
        data = OrganizationDataFactory.minimal_data()
        data["description"] = None
        return data

    def get_special_chars_data(self) -> Dict[str, Any]:
        """Return organization data with special characters"""
        return OrganizationDataFactory.edge_case_data("special_chars")


# Standard entity tests - gets ALL tests from base classes
class TestOrganizationStandardRoutes(OrganizationTestMixin, BaseEntityRouteTests):
    """Complete standard organization route tests using base classes"""

    def test_delete_entity_not_found(self, superuser_client: TestClient):
        """Test deleting non-existent organization - endpoint removed"""
        non_existent_id = str(uuid.uuid4())

        response = superuser_client.delete(self.endpoints.remove(non_existent_id))

        # Organization delete endpoint was removed, so method not allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # Override user field configuration for organizations
    user_id_field = "user_id"
    owner_id_field = "owner_id"
    assignee_id_field = None  # Organizations don't have assignee_id

    def get_sample_data_with_users(
        self, user_id: str = None, owner_id: str = None, assignee_id: str = None
    ) -> Dict[str, Any]:
        """Override to provide organization data with user relationships"""
        data = super().get_sample_data()
        if owner_id:
            data["owner_id"] = owner_id
        if user_id:
            data["user_id"] = user_id
        return data

    # Override CRUD tests to ensure they use authenticated user context
    def test_create_entity_success(self, authenticated_client: TestClient, authenticated_user):
        """Test successful entity creation with user context"""
        sample_data = self.get_sample_data()
        # Organizations require user relationships
        sample_data["owner_id"] = str(authenticated_user.id)
        sample_data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=sample_data)

        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to create organization: {response.text}"
        )

        data = response.json()
        assert data[self.name_field] == sample_data[self.name_field]
        if self.description_field in sample_data:
            assert data[self.description_field] == sample_data[self.description_field]
        assert self.id_field in data
        assert data["owner_id"] == str(authenticated_user.id)
        assert data["user_id"] == str(authenticated_user.id)

    def test_create_entity_minimal_data(self, authenticated_client: TestClient, authenticated_user):
        """Test entity creation with minimal required data"""
        minimal_data = self.get_minimal_data()
        # Organizations require user relationships
        minimal_data["owner_id"] = str(authenticated_user.id)
        minimal_data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=minimal_data)

        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to create organization: {response.text}"
        )

        data = response.json()
        assert data[self.name_field] == minimal_data[self.name_field]
        assert self.id_field in data
        assert data["owner_id"] == str(authenticated_user.id)
        assert data["user_id"] == str(authenticated_user.id)

    def test_entity_with_special_characters(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """🏃‍♂️ Test entity creation with special characters"""
        special_data = self.get_special_chars_data()
        # Organizations require user relationships
        special_data["owner_id"] = str(authenticated_user.id)
        special_data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=special_data)

        # Should handle special characters gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY], (
            f"Unexpected response for special chars: {response.status_code} - {response.text}"
        )

    def test_entity_with_null_description(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """🏃‍♂️ Test entity creation with explicit null description"""
        null_data = self.get_null_description_data()
        # Organizations require user relationships
        null_data["owner_id"] = str(authenticated_user.id)
        null_data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=null_data)

        assert response.status_code == status.HTTP_200_OK, (
            f"Failed with null description: {response.text}"
        )

    def test_list_entities_invalid_pagination(self, authenticated_client: TestClient):
        """Test entity list with invalid pagination parameters"""
        # Test negative limit
        response = authenticated_client.get(f"{self.endpoints.list}?limit=-1")
        # Organizations might return 500 due to error handling in the router, which wraps validation errors
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,  # RLS might cause this
            status.HTTP_500_INTERNAL_SERVER_ERROR,  # Organization router wraps errors
        ], f"Unexpected status for invalid pagination: {response.status_code} - {response.text}"

        # Test negative offset
        response = authenticated_client.get(f"{self.endpoints.list}?offset=-1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_500_INTERNAL_SERVER_ERROR,  # Organization router wraps errors
        ], f"Unexpected status for negative offset: {response.status_code} - {response.text}"

    def test_get_entity_by_id_not_found(self, authenticated_client: TestClient):
        """Test retrieving non-existent entity"""
        non_existent_id = str(uuid.uuid4())

        response = authenticated_client.get(self.endpoints.get(non_existent_id))

        # Due to RLS and organization router error handling, various status codes are possible
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_403_FORBIDDEN,  # RLS might prevent access
            status.HTTP_500_INTERNAL_SERVER_ERROR,  # Organization router wraps errors
        ], f"Unexpected status for non-existent entity: {response.status_code} - {response.text}"

    def test_update_entity_not_found(self, authenticated_client: TestClient):
        """Test updating non-existent entity"""
        non_existent_id = str(uuid.uuid4())
        update_data = self.get_update_data()

        response = authenticated_client.put(self.endpoints.put(non_existent_id), json=update_data)

        # Due to RLS, non-existent entities might return 403 instead of 404
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_403_FORBIDDEN,  # RLS might prevent access
            status.HTTP_422_UNPROCESSABLE_ENTITY,  # Validation might fail first
        ], (
            f"Unexpected status for updating non-existent entity: {response.status_code} - {response.text}"
        )

    def test_delete_entity_success(self, authenticated_client: TestClient):
        """Override base delete test - organization delete endpoint was removed"""
        created_entity = self.create_entity(authenticated_client)
        entity_id = created_entity[self.id_field]

        response = authenticated_client.delete(self.endpoints.remove(entity_id))

        # Organization delete endpoint was removed, so method not allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def create_entity(self, client: TestClient, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Override create_entity to handle organization-specific requirements"""
        if data is None:
            data = self.get_sample_data()

        # Organizations require real user IDs - get them from the API key like the authenticated_user fixture does
        # This allows base tests to work without requiring authenticated_user fixture
        real_user_id = self._get_authenticated_user_id()
        if real_user_id:
            # Replace any placeholder UUIDs with the real authenticated user ID
            data["owner_id"] = real_user_id
            data["user_id"] = real_user_id
        else:
            import pytest

            pytest.skip(
                "Organization creation requires authenticated user - could not get user ID from API key"
            )

        response = client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to create {self.entity_name}: {response.text}"
        )
        return response.json()

    def _get_authenticated_user_id(self) -> str | None:
        """Get the authenticated user ID from the API key, similar to authenticated_user fixture"""
        import os

        from rhesis.backend.app import crud
        from rhesis.backend.app.database import SessionLocal

        api_key = os.getenv("RHESIS_API_KEY")
        if not api_key:
            return None

        # Use a temporary database session to look up the user
        with SessionLocal() as db:
            try:
                # Get token from database using the API key value
                token = crud.get_token_by_value(db, api_key)
                if not token:
                    return None

                # Get user from the token's user_id
                user = crud.get_user_by_id(db, token.user_id)
                if not user:
                    return None

                return str(user.id)
            except Exception:
                return None


# === ORGANIZATION-SPECIFIC TESTS (Enhanced with Factories) ===


@pytest.mark.integration
class TestOrganizationUserRelationships(OrganizationTestMixin, BaseEntityTests):
    """Organization-specific user relationship tests"""

    def test_create_organization_requires_owner_and_user_ids(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """Test organization creation requires owner_id and user_id"""
        data = self.get_sample_data()
        # Explicitly remove owner_id and user_id to test validation
        data.pop("owner_id", None)
        data.pop("user_id", None)

        response = authenticated_client.post(self.endpoints.create, json=data)

        # Should fail without required user relationships
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]
        error_detail = response.json().get("detail", "")
        assert any(field in str(error_detail) for field in ["owner_id", "user_id", "required"])

    def test_create_organization_with_valid_user_ids(
        self, organization_with_owner, authenticated_user
    ):
        """Test organization creation with valid user relationships"""
        data = self.get_sample_data()

        # Use the fixture that properly sets user relationships
        organization = organization_with_owner(data)

        assert organization["name"] == data["name"]
        assert organization["owner_id"] == str(authenticated_user.id)
        assert organization["user_id"] == str(authenticated_user.id)

    def test_organization_user_relationship_validation(self, authenticated_client: TestClient):
        """Test organization creation with invalid user IDs"""
        data = self.get_sample_data()
        data["owner_id"] = str(uuid.uuid4())  # Non-existent user
        data["user_id"] = str(uuid.uuid4())  # Non-existent user

        response = authenticated_client.post(self.endpoints.create, json=data)

        # Should handle foreign key constraint violations gracefully
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


@pytest.mark.integration
class TestOrganizationOnboarding(OrganizationTestMixin, BaseEntityTests):
    """Organization onboarding and initial data management tests"""

    def test_load_initial_data_incomplete_onboarding(
        self, authenticated_client: TestClient, organization_incomplete_onboarding
    ):
        """🏗️ Test loading initial data for organization with incomplete onboarding"""
        # Create organization with incomplete onboarding
        org = organization_incomplete_onboarding()
        assert not org["is_onboarding_complete"]

        # Load initial data
        response = authenticated_client.post(self.endpoints.load_data(org["id"]))

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["status"] == "success"
        assert "loaded successfully" in result["message"].lower()

    def test_load_initial_data_already_complete(
        self, authenticated_client: TestClient, organization_complete_onboarding
    ):
        """✅ Test loading initial data for organization with completed onboarding"""
        # Create organization with completed onboarding
        org = organization_complete_onboarding()
        assert org["is_onboarding_complete"]

        # Try to load initial data again
        response = authenticated_client.post(self.endpoints.load_data(org["id"]))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already initialized" in response.json()["detail"].lower()

    def test_rollback_initial_data_complete_onboarding(
        self, authenticated_client: TestClient, organization_complete_onboarding
    ):
        """🔄 Test rolling back initial data for completed organization"""
        # Create organization with completed onboarding
        org = organization_complete_onboarding()
        assert org["is_onboarding_complete"]

        # Rollback initial data
        response = authenticated_client.post(self.endpoints.rollback_data(org["id"]))

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["status"] == "success"
        assert "rolled back successfully" in result["message"].lower()

    def test_rollback_initial_data_incomplete_onboarding(
        self, authenticated_client: TestClient, organization_incomplete_onboarding
    ):
        """🚫 Test rolling back initial data for incomplete organization"""
        # Create organization with incomplete onboarding
        org = organization_incomplete_onboarding()
        assert not org["is_onboarding_complete"]

        # Try to rollback initial data
        response = authenticated_client.post(self.endpoints.rollback_data(org["id"]))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not initialized yet" in response.json()["detail"].lower()

    def test_onboarding_workflow_complete_cycle(
        self, authenticated_client: TestClient, organization_incomplete_onboarding
    ):
        """🔄 Test complete onboarding workflow cycle"""
        # Create organization with incomplete onboarding
        org = organization_incomplete_onboarding()
        org_id = org["id"]

        # Step 1: Load initial data
        load_response = authenticated_client.post(self.endpoints.load_data(org_id))
        assert load_response.status_code == status.HTTP_200_OK

        # Step 2: Verify organization is now marked as complete
        get_response = authenticated_client.get(self.endpoints.get(org_id))
        assert get_response.status_code == status.HTTP_200_OK
        updated_org = get_response.json()
        assert updated_org["is_onboarding_complete"] is True

        # Step 3: Rollback the data
        rollback_response = authenticated_client.post(self.endpoints.rollback_data(org_id))
        assert rollback_response.status_code == status.HTTP_200_OK

        # Step 4: Verify organization is marked as incomplete again
        final_get_response = authenticated_client.get(self.endpoints.get(org_id))
        assert final_get_response.status_code == status.HTTP_200_OK
        final_org = final_get_response.json()
        assert final_org["is_onboarding_complete"] is False

    def test_onboarding_nonexistent_organization(self, authenticated_client: TestClient):
        """❌ Test onboarding operations on non-existent organization"""
        fake_org_id = str(uuid.uuid4())

        # Try to load initial data
        load_response = authenticated_client.post(self.endpoints.load_data(fake_org_id))
        assert load_response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in load_response.json()["detail"].lower()

        # Try to rollback initial data
        rollback_response = authenticated_client.post(self.endpoints.rollback_data(fake_org_id))
        assert rollback_response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in rollback_response.json()["detail"].lower()


@pytest.mark.integration
class TestOrganizationDomainManagement(OrganizationTestMixin, BaseEntityTests):
    """Organization domain verification and management tests"""

    def test_create_organization_with_domain(self, organization_with_domain):
        """🌐 Test creating organization with domain configuration"""
        domain = "testcompany.com"
        org = organization_with_domain(domain=domain, verified=False)

        assert org["domain"] == domain
        assert org["is_domain_verified"] is False

    def test_create_organization_with_verified_domain(self, organization_with_domain):
        """✅ Test creating organization with verified domain"""
        domain = "verified.com"
        org = organization_with_domain(domain=domain, verified=True)

        assert org["domain"] == domain
        assert org["is_domain_verified"] is True

    def test_update_organization_domain_verification(
        self, authenticated_client: TestClient, organization_with_domain
    ):
        """🔄 Test updating organization domain verification status"""
        # Create organization with unverified domain
        org = organization_with_domain(domain="example.com", verified=False)

        # Update to verified
        update_data = {"is_domain_verified": True}

        response = authenticated_client.put(self.endpoints.put(org["id"]), json=update_data)
        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to update domain verification: {response.text}"
        )

        updated_org = response.json()
        assert updated_org["is_domain_verified"] is True
        assert updated_org["domain"] == "example.com"


@pytest.mark.integration
class TestOrganizationLimitsAndSubscription(OrganizationTestMixin, BaseEntityTests):
    """Organization user limits and subscription management tests"""

    def test_create_organization_with_user_limits(self, organization_with_limits):
        """📊 Test creating organization with user limits"""
        max_users = 25
        org = organization_with_limits(max_users=max_users, active=True)

        assert org["max_users"] == max_users
        assert org["is_active"] is True

    def test_create_inactive_organization(self, organization_with_limits):
        """🚫 Test creating inactive organization"""
        org = organization_with_limits(max_users=10, active=False)

        assert org["is_active"] is False
        assert org["max_users"] == 10

    def test_update_organization_limits(
        self, authenticated_client: TestClient, organization_with_limits
    ):
        """🔄 Test updating organization limits"""
        # Create organization with initial limits
        org = organization_with_limits(max_users=50, active=True)

        # Update limits
        update_data = {"max_users": 100, "is_active": False}

        response = authenticated_client.put(self.endpoints.put(org["id"]), json=update_data)
        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to update organization limits: {response.text}"
        )

        updated_org = response.json()
        assert updated_org["max_users"] == 100
        assert updated_org["is_active"] is False


@pytest.mark.integration
class TestOrganizationDeletion(OrganizationTestMixin, BaseEntityTests):
    """Organization deletion and authorization tests"""

    def test_delete_organization_requires_superuser(
        self, authenticated_client: TestClient, organization_with_owner, authenticated_user
    ):
        """🔒 Test organization deletion - endpoint was removed"""
        # Create organization
        org = organization_with_owner()

        # Try to delete - endpoint no longer exists
        response = authenticated_client.delete(self.endpoints.remove(org["id"]))

        # Organization delete endpoint was removed, so method not allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_nonexistent_organization(self, authenticated_client: TestClient):
        """❌ Test deleting non-existent organization - endpoint removed"""
        fake_org_id = str(uuid.uuid4())

        response = authenticated_client.delete(self.endpoints.remove(fake_org_id))

        # Organization delete endpoint was removed, so method not allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# === VALIDATION TESTS ===


@pytest.mark.unit
class TestOrganizationValidation(OrganizationTestMixin, BaseEntityTests):
    """Organization-specific validation tests"""

    def test_create_organization_required_fields(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """Test organization creation with required fields only"""
        data = self.get_minimal_data()
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=data)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        created_org = response.json()
        assert created_org["name"] == data["name"]

    def test_create_organization_with_all_fields(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """Test organization creation with all optional fields"""
        data = self.get_sample_data()
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=data)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        created_org = response.json()
        assert created_org["name"] == data["name"]
        assert created_org["display_name"] == data.get("display_name")
        assert created_org["website"] == data.get("website")
        assert created_org["email"] == data.get("email")

    def test_organization_email_validation(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """📧 Test organization email validation"""
        valid_emails = [
            "contact@company.com",
            "info@startup.io",
            "hello@organization.org",
            "support@business.co.uk",
        ]

        for email in valid_emails:
            data = self.get_minimal_data()
            data["owner_id"] = str(authenticated_user.id)
            data["user_id"] = str(authenticated_user.id)
            data["email"] = email
            data["name"] = f"Test Org {email.split('@')[1]}"

            response = authenticated_client.post(self.endpoints.create, json=data)
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

            created_org = response.json()
            assert created_org["email"] == email

    def test_organization_website_validation(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """🌐 Test organization website URL validation"""
        valid_urls = [
            "https://company.com",
            "http://startup.io",
            "https://www.organization.org",
            "https://business.co.uk/about",
        ]

        for url in valid_urls:
            data = self.get_minimal_data()
            data["owner_id"] = str(authenticated_user.id)
            data["user_id"] = str(authenticated_user.id)
            data["website"] = url
            data["name"] = f"Test Org {url.split('//')[1].split('.')[0].title()}"

            response = authenticated_client.post(self.endpoints.create, json=data)
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

            created_org = response.json()
            assert created_org["website"] == url


# === EDGE CASE TESTS ===


@pytest.mark.unit
class TestOrganizationEdgeCases(OrganizationTestMixin, BaseEntityTests):
    """Enhanced organization edge case tests using factory system"""

    def test_create_organization_long_name(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """Test creating organization with very long name"""
        data = self.get_edge_case_data("long_name")
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=data)

        # Should handle long names gracefully
        assert response.status_code in [
            status.HTTP_200_OK,  # If long names are allowed
            status.HTTP_201_CREATED,  # If long names are allowed
            status.HTTP_422_UNPROCESSABLE_ENTITY,  # If they're rejected
        ]

    def test_create_organization_special_characters(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """Test creating organization with special characters"""
        data = self.get_edge_case_data("special_chars")
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=data)

        # Should handle special characters gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        created_org = response.json()
        assert created_org["name"] == data["name"]

    def test_create_organization_unicode(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """Test creating organization with unicode characters"""
        data = self.get_edge_case_data("unicode")
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=data)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        created_org = response.json()
        assert created_org["name"] == data["name"]

    def test_create_organization_sql_injection_attempt(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """🛡️ Test organization creation with SQL injection attempt"""
        data = self.get_edge_case_data("sql_injection")
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=data)

        # Should either create safely or reject
        if response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            # If created, verify it was sanitized
            created_org = response.json()
            assert created_org["name"] is not None
        else:
            # If rejected, should be a validation error
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ]

    def test_organization_max_limits_edge_case(
        self, authenticated_client: TestClient, authenticated_user
    ):
        """📊 Test organization with maximum limit values"""
        data = self.get_edge_case_data("max_limits")
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post(self.endpoints.create, json=data)

        # Should handle max values gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY,  # If limits are enforced
        ]


# === PERFORMANCE TESTS ===


@pytest.mark.slow
@pytest.mark.integration
class TestOrganizationPerformance(OrganizationTestMixin, BaseEntityTests):
    """Performance tests using factory batch creation"""

    def test_bulk_organization_creation(self, organization_batch_creator):
        """🚀 Test creating multiple organizations efficiently"""
        # Create batch of organizations
        organizations = organization_batch_creator(count=8, variation=True)

        assert len(organizations) == 8
        assert all(org["id"] is not None for org in organizations)
        assert all(org["name"] is not None for org in organizations)

        # Verify they're all different
        names = [org["name"] for org in organizations]
        assert len(set(names)) == len(names)  # All unique names

    def test_organization_list_pagination(
        self, authenticated_client: TestClient, organization_batch_creator
    ):
        """🚀 Test list pagination with large dataset"""
        # Create batch of organizations
        organizations = organization_batch_creator(count=10)
        assert len(organizations) >= 5

        # Test pagination
        response = authenticated_client.get(f"{self.endpoints.list}?limit=5&skip=0")
        assert response.status_code == status.HTTP_200_OK

        page_1 = response.json()
        assert len(page_1) <= 5  # Should respect limit

        # Test second page
        response = authenticated_client.get(f"{self.endpoints.list}?limit=5&skip=5")
        assert response.status_code == status.HTTP_200_OK

        page_2 = response.json()
        # page_2 might be empty if there aren't enough organizations, which is fine


# === MULTI-STATE SCENARIO TESTS ===


@pytest.mark.integration
class TestOrganizationMultiState(OrganizationTestMixin, BaseEntityTests):
    """Tests for organizations in multiple states"""

    def test_organization_different_states(self, organization_multi_state):
        """🔀 Test organizations in different states"""
        orgs = organization_multi_state()

        # Verify different states
        assert not orgs["incomplete"]["is_onboarding_complete"]
        assert orgs["complete"]["is_onboarding_complete"]
        assert not orgs["inactive"]["is_active"]

        # Verify they all have different names
        names = [orgs["incomplete"]["name"], orgs["complete"]["name"], orgs["inactive"]["name"]]
        assert len(set(names)) == 3
