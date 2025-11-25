"""
🏢 Organization Entity Fixtures

Specialized fixtures for organization entities with proper user relationships,
onboarding state management, and domain verification handling.

These fixtures handle the complex organization creation requirements including:
- User ownership relationships (owner_id and user_id)
- Onboarding state management
- Domain verification
- Initial data loading/rollback
"""

import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient

from ..data_factories import OrganizationDataFactory


@pytest.fixture
def organization_with_owner(authenticated_client: TestClient, authenticated_user):
    """🏢 Organization with proper owner relationship"""

    def _create_organization_with_owner(data: Dict[str, Any] = None) -> Dict[str, Any]:
        if data is None:
            data = OrganizationDataFactory.sample_data()

        # Set the owner and user IDs to the authenticated user
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)

        response = authenticated_client.post("/organizations/", json=data)
        assert response.status_code in [200, 201], f"Failed to create organization: {response.text}"

        return response.json()

    return _create_organization_with_owner


@pytest.fixture
def organization_incomplete_onboarding(authenticated_client: TestClient, authenticated_user):
    """🏗️ Organization with incomplete onboarding"""

    def _create_incomplete_org(data: Dict[str, Any] = None) -> Dict[str, Any]:
        if data is None:
            data = OrganizationDataFactory.onboarding_incomplete_data()

        # Set the owner and user IDs
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)
        data["is_onboarding_complete"] = False

        response = authenticated_client.post("/organizations/", json=data)
        assert response.status_code in [200, 201], f"Failed to create organization: {response.text}"

        return response.json()

    return _create_incomplete_org


@pytest.fixture
def organization_complete_onboarding(authenticated_client: TestClient, authenticated_user):
    """Organization with completed onboarding"""

    def _create_complete_org(data: Dict[str, Any] = None) -> Dict[str, Any]:
        if data is None:
            data = OrganizationDataFactory.onboarding_complete_data()

        # Set the owner and user IDs
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)
        data["is_onboarding_complete"] = True

        response = authenticated_client.post("/organizations/", json=data)
        assert response.status_code in [200, 201], f"Failed to create organization: {response.text}"

        return response.json()

    return _create_complete_org


@pytest.fixture
def organization_with_domain(authenticated_client: TestClient, authenticated_user):
    """🌐 Organization with domain configuration"""

    def _create_domain_org(domain: str = "example.com", verified: bool = False) -> Dict[str, Any]:
        data = OrganizationDataFactory.sample_data()
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)
        data["domain"] = domain
        data["is_domain_verified"] = verified

        response = authenticated_client.post("/organizations/", json=data)
        assert response.status_code in [200, 201], f"Failed to create organization: {response.text}"

        return response.json()

    return _create_domain_org


@pytest.fixture
def organization_with_limits(authenticated_client: TestClient, authenticated_user):
    """Organization with user limits and subscription"""

    def _create_limited_org(max_users: int = 50, active: bool = True) -> Dict[str, Any]:
        data = OrganizationDataFactory.sample_data()
        data["owner_id"] = str(authenticated_user.id)
        data["user_id"] = str(authenticated_user.id)
        data["max_users"] = max_users
        data["is_active"] = active

        response = authenticated_client.post("/organizations/", json=data)
        assert response.status_code in [200, 201], f"Failed to create organization: {response.text}"

        return response.json()

    return _create_limited_org


@pytest.fixture
def organization_batch_creator(authenticated_client: TestClient, authenticated_user):
    """Batch organization creator for performance tests"""

    def _create_organization_batch(count: int = 5, variation: bool = True) -> list:
        organizations = []

        for i in range(count):
            if variation:
                data = OrganizationDataFactory.sample_data()
                data["name"] = f"Test Organization {i + 1}"
            else:
                data = OrganizationDataFactory.minimal_data()
                data["name"] = f"Minimal Org {i + 1}"

            # Set required user relationships
            data["owner_id"] = str(authenticated_user.id)
            data["user_id"] = str(authenticated_user.id)

            response = authenticated_client.post("/organizations/", json=data)
            assert response.status_code in [200, 201], (
                f"Failed to create organization {i + 1}: {response.text}"
            )

            organizations.append(response.json())

        return organizations

    return _create_organization_batch


# Composite fixtures for complex testing scenarios


@pytest.fixture
def organization_onboarding_scenario(organization_incomplete_onboarding):
    """Complete organization onboarding scenario fixture"""
    # Create organization with incomplete onboarding
    org = organization_incomplete_onboarding()

    return {"organization": org, "is_ready_for_onboarding": not org["is_onboarding_complete"]}


@pytest.fixture
def organization_multi_state(authenticated_client: TestClient, authenticated_user):
    """🔀 Multiple organizations in different states"""

    def _create_multi_state():
        # Create organizations in different states
        incomplete_data = OrganizationDataFactory.onboarding_incomplete_data()
        incomplete_data["owner_id"] = str(authenticated_user.id)
        incomplete_data["user_id"] = str(authenticated_user.id)
        incomplete_data["name"] = "Incomplete Onboarding Org"

        complete_data = OrganizationDataFactory.onboarding_complete_data()
        complete_data["owner_id"] = str(authenticated_user.id)
        complete_data["user_id"] = str(authenticated_user.id)
        complete_data["name"] = "Complete Onboarding Org"

        inactive_data = OrganizationDataFactory.sample_data()
        inactive_data["owner_id"] = str(authenticated_user.id)
        inactive_data["user_id"] = str(authenticated_user.id)
        inactive_data["name"] = "Inactive Org"
        inactive_data["is_active"] = False

        # Create all organizations
        incomplete_response = authenticated_client.post("/organizations/", json=incomplete_data)
        complete_response = authenticated_client.post("/organizations/", json=complete_data)
        inactive_response = authenticated_client.post("/organizations/", json=inactive_data)

        assert all(
            r.status_code in [200, 201]
            for r in [incomplete_response, complete_response, inactive_response]
        )

        return {
            "incomplete": incomplete_response.json(),
            "complete": complete_response.json(),
            "inactive": inactive_response.json(),
        }

    return _create_multi_state
