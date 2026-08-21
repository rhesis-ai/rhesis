"""
Tests for DELETE /endpoints/bulk endpoint.

Registered before /{endpoint_id} in routers/endpoint.py -- these tests exist mainly to
guard against that route-ordering regression (a /{endpoint_id}-shaped route
registered first would swallow "/endpoints/bulk", treating "bulk" as an id).
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.endpoint import Endpoint


class TestBulkDeleteEndpointsEndpoint:
    """Tests for DELETE /endpoints/bulk"""

    def test_bulk_delete_returns_deleted_and_not_found_ids(
        self, authenticated_client: TestClient, db_endpoint_minimal
    ):
        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/endpoints/bulk",
            json={"endpoint_ids": [str(db_endpoint_minimal.id), fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [str(db_endpoint_minimal.id)]
        assert data["not_found_ids"] == [fake_id]

    def test_bulk_delete_bumps_updated_at(
        self, authenticated_client: TestClient, db_endpoint_minimal, test_db: Session
    ):
        """bulk_delete_by_ids soft-deletes via a Core-level query.update(),
        which bypasses the ORM flush path that applies column onupdate for a
        single-row soft_delete() -- without setting updated_at explicitly,
        it stays stale after a bulk delete even though deleted_at is correct.
        """
        original_updated_at = db_endpoint_minimal.updated_at
        test_db.commit()

        response = authenticated_client.request(
            "DELETE",
            "/endpoints/bulk",
            json={"endpoint_ids": [str(db_endpoint_minimal.id)]},
        )
        assert response.status_code == status.HTTP_200_OK

        test_db.expire_all()
        with without_soft_delete_filter():
            deleted_endpoint = (
                test_db.query(Endpoint).filter(Endpoint.id == db_endpoint_minimal.id).first()
            )
        assert deleted_endpoint is not None
        assert deleted_endpoint.updated_at > original_updated_at

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request(
            "DELETE", "/endpoints/bulk", json={"endpoint_ids": [str(uuid.uuid4())]}
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
