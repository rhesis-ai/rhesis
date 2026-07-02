"""Tests for PUT /test_sets/{test_set_identifier}.

The update route resolves its identifier the same way the read routes do
(UUID, nano_id, or slug), so a test set can be updated without first
resolving it to a UUID.
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestUpdateTestSet:
    """Tests for PUT /test_sets/{test_set_identifier}"""

    def test_update_by_uuid(self, authenticated_client: TestClient, db_test_set):
        """Updating by UUID still works (backward-compatible path)."""
        response = authenticated_client.put(
            f"/test_sets/{db_test_set.id}",
            json={"name": "Updated By UUID"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated By UUID"

    def test_update_by_slug(
        self, authenticated_client: TestClient, test_db: Session, db_test_set
    ):
        """Updating by slug resolves the test set without a UUID."""
        db_test_set.slug = "my-update-slug"
        test_db.add(db_test_set)
        test_db.flush()

        response = authenticated_client.put(
            f"/test_sets/{db_test_set.slug}",
            json={"name": "Updated By Slug"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == str(db_test_set.id)
        assert body["name"] == "Updated By Slug"

    def test_update_unknown_identifier_returns_404(self, authenticated_client: TestClient):
        """An identifier that resolves to nothing returns 404."""
        response = authenticated_client.put(
            f"/test_sets/{uuid.uuid4()}",
            json={"name": "Nope"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
