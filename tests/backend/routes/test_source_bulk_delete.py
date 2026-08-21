"""
Tests for DELETE /sources/bulk endpoint.

Registered before /{source_id} in routers/source.py -- these tests exist mainly to
guard against that route-ordering regression (a /{source_id}-shaped route
registered first would swallow "/sources/bulk", treating "bulk" as an id).
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.source import Source


class TestBulkDeleteSourcesEndpoint:
    """Tests for DELETE /sources/bulk"""

    def test_bulk_delete_returns_deleted_and_not_found_ids(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_organization,
        authenticated_user_id: str,
    ):
        source = Source(
            title="Bulk-delete source",
            organization_id=test_organization.id,
            user_id=authenticated_user_id,
        )
        test_db.add(source)
        test_db.flush()
        test_db.refresh(source)

        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/sources/bulk",
            json={"source_ids": [str(source.id), fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [str(source.id)]
        assert data["not_found_ids"] == [fake_id]

    def test_bulk_delete_bumps_updated_at(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_organization,
        authenticated_user_id: str,
    ):
        """bulk_delete_by_ids soft-deletes via a Core-level query.update(),
        which bypasses the ORM flush path that applies column onupdate for a
        single-row soft_delete() -- without setting updated_at explicitly,
        it stays stale after a bulk delete even though deleted_at is correct.
        """
        source = Source(
            title="Bulk-delete source",
            organization_id=test_organization.id,
            user_id=authenticated_user_id,
        )
        test_db.add(source)
        test_db.flush()
        test_db.refresh(source)
        original_updated_at = source.updated_at
        test_db.commit()

        response = authenticated_client.request(
            "DELETE",
            "/sources/bulk",
            json={"source_ids": [str(source.id)]},
        )
        assert response.status_code == status.HTTP_200_OK

        test_db.expire_all()
        with without_soft_delete_filter():
            deleted_source = test_db.query(Source).filter(Source.id == source.id).first()
        assert deleted_source is not None
        assert deleted_source.updated_at > original_updated_at

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request(
            "DELETE", "/sources/bulk", json={"source_ids": [str(uuid.uuid4())]}
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
