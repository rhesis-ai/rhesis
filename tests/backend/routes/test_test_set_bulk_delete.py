"""
Tests for DELETE /test_sets/bulk endpoint.

Registered before /{test_set_id} in routers/test_set.py -- these tests exist mainly to
guard against that route-ordering regression (a /{test_set_id}-shaped route
registered first would swallow "/test_sets/bulk", treating "bulk" as an id).
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.test_set import TestSet


class TestBulkDeleteTestSetsEndpoint:
    """Tests for DELETE /test_sets/bulk"""

    def test_bulk_delete_returns_deleted_and_not_found_ids(
        self, authenticated_client: TestClient, db_test_set
    ):
        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/test_sets/bulk",
            json={"test_set_ids": [str(db_test_set.id), fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [str(db_test_set.id)]
        assert data["not_found_ids"] == [fake_id]

    def test_bulk_delete_bumps_updated_at(
        self, authenticated_client: TestClient, db_test_set, test_db: Session
    ):
        """bulk_delete_by_ids soft-deletes via a Core-level query.update(),
        which bypasses the ORM flush path that applies column onupdate for a
        single-row soft_delete() -- without setting updated_at explicitly,
        it stays stale after a bulk delete even though deleted_at is correct.
        """
        original_updated_at = db_test_set.updated_at
        test_db.commit()

        response = authenticated_client.request(
            "DELETE",
            "/test_sets/bulk",
            json={"test_set_ids": [str(db_test_set.id)]},
        )
        assert response.status_code == status.HTTP_200_OK

        test_db.expire_all()
        with without_soft_delete_filter():
            deleted_test_set = (
                test_db.query(TestSet).filter(TestSet.id == db_test_set.id).first()
            )
        assert deleted_test_set is not None
        assert deleted_test_set.updated_at > original_updated_at

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request(
            "DELETE", "/test_sets/bulk", json={"test_set_ids": [str(uuid.uuid4())]}
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
