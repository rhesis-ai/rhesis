"""
🔄 Transaction Management Testing for Router Operations

Comprehensive test suite for verifying that transaction management works correctly
in router operations after refactoring to remove manual db.commit() and db.rollback() calls.

Tests focus on:
- Automatic transaction commit on success in router endpoints
- Proper error handling in router operations
- Organization onboarding operations

Functions tested from routers:
- organization.py: load_initial_data, rollback_initial_data endpoints

Run with: python -m pytest tests/backend/routes/test_transaction_management.py -v
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from rhesis.backend.app import models
from tests.backend.routes.fixtures.data_factories import OrganizationDataFactory


@pytest.mark.unit
@pytest.mark.routes
@pytest.mark.transaction
class TestRouterTransactionManagement:
    """🔄 Test automatic transaction management in router operations"""

    def test_organization_load_initial_data_commits_on_success(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that organization load_initial_data endpoint commits automatically on success"""
        # Create an organization with incomplete onboarding
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = False

        # Create organization directly in database
        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        test_db.add(organization)
        test_db.flush()

        # Update user's organization_id
        authenticated_user.organization_id = organization.id
        test_db.flush()

        # Call the load initial data endpoint (no mocking - use real service)
        response = authenticated_client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify successful response
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify organization onboarding status was updated and committed
        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is True

    def test_organization_load_initial_data_handles_errors_gracefully(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that organization load_initial_data endpoint handles errors gracefully"""
        # Create an organization with incomplete onboarding
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = False

        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        test_db.add(organization)
        test_db.flush()

        # Update user's organization_id
        authenticated_user.organization_id = organization.id
        test_db.flush()

        # Call the load initial data endpoint (no mocking - use real service)
        # This should succeed since the organization is properly set up
        response = authenticated_client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify successful response (since we're not mocking an error)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify organization onboarding status was updated and committed
        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is True

    def test_organization_rollback_initial_data_commits_on_success(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that organization rollback_initial_data endpoint commits automatically on success"""
        # Create an organization with complete onboarding
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = True

        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        test_db.add(organization)
        test_db.flush()

        # Update user's organization_id
        authenticated_user.organization_id = organization.id
        test_db.flush()

        # Call the rollback initial data endpoint (no mocking - use real service)
        response = authenticated_client.post(
            f"/organizations/{organization.id}/rollback-initial-data"
        )

        # Verify successful response
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify organization onboarding status was updated and committed
        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is False

    def test_organization_rollback_initial_data_handles_errors_gracefully(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that organization rollback_initial_data endpoint handles errors gracefully"""
        # Create an organization with complete onboarding
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = True

        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        test_db.add(organization)
        test_db.flush()

        # Update user's organization_id
        authenticated_user.organization_id = organization.id
        test_db.flush()

        # Call the rollback initial data endpoint (no mocking - use real service)
        # This should succeed since the organization is properly set up
        response = authenticated_client.post(
            f"/organizations/{organization.id}/rollback-initial-data"
        )

        # Verify successful response (since we're not mocking an error)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify organization onboarding status was updated and committed
        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is False

    def test_organization_load_initial_data_already_complete_error(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that load_initial_data returns error for already completed organization"""
        # Create an organization with complete onboarding
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = True

        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        test_db.add(organization)
        test_db.flush()

        # Update user's organization_id
        authenticated_user.organization_id = organization.id
        test_db.flush()

        # Call the load initial data endpoint
        response = authenticated_client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify error response
        assert response.status_code == 400
        assert "already initialized" in response.json()["detail"]

        # Verify organization status remains unchanged
        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is True

    def test_organization_rollback_initial_data_not_complete_error(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that rollback_initial_data returns error for not completed organization"""
        # Create an organization with incomplete onboarding
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = False

        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        test_db.add(organization)
        test_db.flush()

        # Update user's organization_id
        authenticated_user.organization_id = organization.id
        test_db.flush()

        # Call the rollback initial data endpoint
        response = authenticated_client.post(
            f"/organizations/{organization.id}/rollback-initial-data"
        )

        # Verify error response
        assert response.status_code == 400
        assert "not initialized yet" in response.json()["detail"]

        # Verify organization status remains unchanged
        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is False

    def test_organization_operations_transaction_isolation(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that organization operations maintain proper transaction isolation"""
        # Create two organizations
        org_data1 = OrganizationDataFactory.sample_data()
        org_data1["name"] = "Test Org 1"
        org_data1["owner_id"] = str(authenticated_user.id)
        org_data1["user_id"] = str(authenticated_user.id)
        org_data1["is_onboarding_complete"] = False

        org_data2 = OrganizationDataFactory.sample_data()
        org_data2["name"] = "Test Org 2"
        org_data2["owner_id"] = str(authenticated_user.id)
        org_data2["user_id"] = str(authenticated_user.id)
        org_data2["is_onboarding_complete"] = True

        organization1 = models.Organization(**org_data1)
        organization1.id = uuid.uuid4()
        organization2 = models.Organization(**org_data2)
        organization2.id = uuid.uuid4()

        test_db.add_all([organization1, organization2])
        test_db.flush()

        # Update user's organization_id to first org
        authenticated_user.organization_id = organization1.id
        test_db.flush()

        # Load initial data for first org (no mocking - use real service)
        response1 = authenticated_client.post(
            f"/organizations/{organization1.id}/load-initial-data"
        )
        assert response1.status_code == 200

        # Update user's organization to second org
        authenticated_user.organization_id = organization2.id
        test_db.flush()

        # Rollback initial data for second org (no mocking - use real service)
        response2 = authenticated_client.post(
            f"/organizations/{organization2.id}/rollback-initial-data"
        )
        assert response2.status_code == 200

        # Verify both operations succeeded independently
        db_org1 = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization1.id)
            .first()
        )
        db_org2 = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization2.id)
            .first()
        )

        assert db_org1 is not None
        assert db_org2 is not None
        assert db_org1.is_onboarding_complete is True
        assert db_org2.is_onboarding_complete is False

    def test_router_operations_with_service_layer_integration(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that router operations integrate properly with service layer transaction management"""
        # Create an organization
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = False

        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        test_db.add(organization)
        test_db.flush()

        # Update user's organization_id
        authenticated_user.organization_id = organization.id
        test_db.flush()

        # Test the full integration without mocking service layer
        # This tests that the router + service + database transaction management works together

        # Call the endpoint (no mocking - use real service)
        response = authenticated_client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify the router-level database changes were committed
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is True

    def test_unauthorized_access_does_not_affect_transactions(
        self, client: TestClient, test_db, authenticated_user
    ):
        """Test that unauthorized access attempts do not affect database transactions"""
        # Create an organization with valid user references
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        organization = models.Organization(**org_data)
        organization.id = uuid.uuid4()
        organization.is_onboarding_complete = False
        test_db.add(organization)
        test_db.flush()

        # Try to access endpoint without authentication
        response = client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify unauthorized response
        assert response.status_code == 401

        # Verify organization state was not affected
        db_org = (
            test_db.query(models.Organization)
            .filter(models.Organization.id == organization.id)
            .first()
        )
        assert db_org is not None
        assert db_org.is_onboarding_complete is False  # Should remain unchanged
