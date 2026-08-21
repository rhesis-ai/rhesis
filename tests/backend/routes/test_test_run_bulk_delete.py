"""
Tests for DELETE /test_runs/bulk endpoint.

Registered before /{test_run_id} in routers/test_run.py -- these tests guard
against that route-ordering regression, and against the owner-only delete
rule (only the creator may delete a test run) being silently dropped for the
bulk path the way a naive bulk_delete_by_ids() call would: TestRun has no
visibility column, so without the owner_attr filter any org member could
bulk-delete anyone's test runs.
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.test_run import TestRun


class TestBulkDeleteTestRunsEndpoint:
    """Tests for DELETE /test_runs/bulk"""

    def test_bulk_delete_buckets_owned_forbidden_and_not_found_ids(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_organization,
        authenticated_user_id: str,
        db_status,
        db_test_configuration,
        db_test_run,
    ):
        """One id owned by the caller, one owned by someone else (same org),
        and one that doesn't exist -- each must land in exactly one bucket.
        ``db_test_run`` is created for a different user than the caller (see
        its fixture), so it doubles as the "forbidden" case here.
        """
        owned_run = TestRun(
            name="Caller's run",
            user_id=authenticated_user_id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            test_configuration_id=db_test_configuration.id,
        )
        test_db.add(owned_run)
        test_db.flush()
        test_db.refresh(owned_run)

        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/test_runs/bulk",
            json={"test_run_ids": [str(owned_run.id), str(db_test_run.id), fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [str(owned_run.id)]
        assert data["forbidden_ids"] == [str(db_test_run.id)]
        assert data["not_found_ids"] == [fake_id]

        test_db.expire_all()
        with without_soft_delete_filter():
            still_present = (
                test_db.query(TestRun).filter(TestRun.id == db_test_run.id).first()
            )
        # Forbidden id must not be deleted, unlike not_found ids which never existed.
        assert still_present is not None
        assert still_present.deleted_at is None

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request(
            "DELETE", "/test_runs/bulk", json={"test_run_ids": [str(uuid.uuid4())]}
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
