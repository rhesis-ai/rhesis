"""
Tests for DELETE /tests/bulk endpoint.

Registered before /{test_id} in routers/test.py -- these tests exist mainly to
guard against that route-ordering regression (a /{test_id}-shaped route
registered first would swallow "/tests/bulk", treating "bulk" as an id).
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.test import Test


class TestBulkDeleteTestsEndpoint:
    """Tests for DELETE /tests/bulk"""

    def test_bulk_delete_returns_deleted_and_not_found_ids(
        self, authenticated_client: TestClient, db_test_minimal
    ):
        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/tests/bulk",
            json={"test_ids": [str(db_test_minimal.id), fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [str(db_test_minimal.id)]
        assert data["not_found_ids"] == [fake_id]

    def test_bulk_delete_bumps_updated_at(
        self, authenticated_client: TestClient, db_test_minimal, test_db: Session
    ):
        """bulk_delete_by_ids soft-deletes via a Core-level query.update(),
        which bypasses the ORM flush path that applies column onupdate for a
        single-row soft_delete() -- without setting updated_at explicitly,
        it stays stale after a bulk delete even though deleted_at is correct.
        """
        original_updated_at = db_test_minimal.updated_at
        # Postgres's CURRENT_TIMESTAMP is fixed for the lifetime of a
        # transaction, not per-statement -- commit so the delete below runs
        # in a new transaction, same as two separate real requests.
        test_db.commit()

        response = authenticated_client.request(
            "DELETE",
            "/tests/bulk",
            json={"test_ids": [str(db_test_minimal.id)]},
        )
        assert response.status_code == status.HTTP_200_OK

        test_db.expire_all()
        with without_soft_delete_filter():
            deleted_test = test_db.query(Test).filter(Test.id == db_test_minimal.id).first()
        assert deleted_test is not None
        assert deleted_test.updated_at > original_updated_at

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request("DELETE", "/tests/bulk", json={"test_ids": [str(uuid.uuid4())]})
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
