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
from tests.backend.fixtures.rls import scope_to_org
from tests.backend.routes.fixtures.data_factories import OrganizationDataFactory


def _insert_test_org(test_db, **org_data):
    """Create an org, scoping the session to it first.

    INSERT RETURNING evaluates the USING clause, so the GUC has to match the
    new org before the flush, not after.
    """
    organization = models.Organization(**org_data)
    organization.id = uuid.uuid4()
    test_db.add(organization)
    scope_to_org(test_db, organization.id)
    test_db.flush()
    return organization


@pytest.mark.unit
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

        organization = _insert_test_org(test_db, **org_data)

        authenticated_user.organization_id = organization.id
        test_db.flush()

        response = authenticated_client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify successful response
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify organization onboarding status was updated and committed. The
        # endpoint ran through the HTTP client's own session, not test_db --
        # expire test_db's cached copy so this re-reads the committed row.
        test_db.expire_all()
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

        organization = _insert_test_org(test_db, **org_data)

        authenticated_user.organization_id = organization.id
        test_db.flush()

        response = authenticated_client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify successful response (since we're not mocking an error)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify organization onboarding status was updated and committed. The
        # endpoint ran through the HTTP client's own session, not test_db --
        # expire test_db's cached copy so this re-reads the committed row.
        test_db.expire_all()
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

        organization = _insert_test_org(test_db, **org_data)

        authenticated_user.organization_id = organization.id
        test_db.flush()

        response = authenticated_client.post(
            f"/organizations/{organization.id}/rollback-initial-data"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        test_db.expire_all()
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
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = True

        organization = _insert_test_org(test_db, **org_data)

        authenticated_user.organization_id = organization.id
        test_db.flush()

        response = authenticated_client.post(
            f"/organizations/{organization.id}/rollback-initial-data"
        )

        # Verify successful response (since we're not mocking an error)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify organization onboarding status was updated and committed. The
        # endpoint ran through the HTTP client's own session, not test_db --
        # expire test_db's cached copy so this re-reads the committed row.
        test_db.expire_all()
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
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = True

        organization = _insert_test_org(test_db, **org_data)

        authenticated_user.organization_id = organization.id
        test_db.flush()

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
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = False

        organization = _insert_test_org(test_db, **org_data)

        authenticated_user.organization_id = organization.id
        test_db.flush()

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

        organization1 = _insert_test_org(test_db, **org_data1)
        organization2 = _insert_test_org(test_db, **org_data2)

        # Switch to org1 for load-initial-data
        scope_to_org(test_db, organization1.id)
        authenticated_user.organization_id = organization1.id
        test_db.flush()

        response1 = authenticated_client.post(
            f"/organizations/{organization1.id}/load-initial-data"
        )
        assert response1.status_code == 200

        # Switch to org2 for rollback-initial-data
        scope_to_org(test_db, organization2.id)
        authenticated_user.organization_id = organization2.id
        test_db.flush()

        response2 = authenticated_client.post(
            f"/organizations/{organization2.id}/rollback-initial-data"
        )
        assert response2.status_code == 200

        test_db.expire_all()
        # A blank org GUC makes the organization table's USING clause return
        # TRUE for every row, so both orgs are visible for verification.
        scope_to_org(test_db, None)
        org1_id = organization1.id
        org2_id = organization2.id
        db_org1 = (
            test_db.query(models.Organization).filter(models.Organization.id == org1_id).first()
        )
        db_org2 = (
            test_db.query(models.Organization).filter(models.Organization.id == org2_id).first()
        )

        assert db_org1 is not None
        assert db_org2 is not None
        assert db_org1.is_onboarding_complete is True
        assert db_org2.is_onboarding_complete is False

    def test_router_operations_with_service_layer_integration(
        self, authenticated_client: TestClient, authenticated_user, test_db
    ):
        """Test that router operations integrate properly with service layer transaction management"""
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = False

        organization = _insert_test_org(test_db, **org_data)

        authenticated_user.organization_id = organization.id
        test_db.flush()

        response = authenticated_client.post(f"/organizations/{organization.id}/load-initial-data")

        # Verify the router-level database changes were committed. The
        # endpoint ran through the HTTP client's own session, not test_db --
        # expire test_db's cached copy so this re-reads the committed row.
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        test_db.expire_all()
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
        org_data = OrganizationDataFactory.sample_data()
        org_data["owner_id"] = str(authenticated_user.id)
        org_data["user_id"] = str(authenticated_user.id)
        org_data["is_onboarding_complete"] = False
        organization = _insert_test_org(test_db, **org_data)

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
