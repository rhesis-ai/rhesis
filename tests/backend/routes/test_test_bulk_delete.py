"""
Tests for DELETE /tests/bulk endpoint.

Registered before /{test_id} in routers/test.py -- these tests exist mainly to
guard against that route-ordering regression (a /{test_id}-shaped route
registered first would swallow "/tests/bulk", treating "bulk" as an id).
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient


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

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request("DELETE", "/tests/bulk", json={"test_ids": [str(uuid.uuid4())]})
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
