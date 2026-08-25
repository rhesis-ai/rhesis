"""
Tests for DELETE /tokens/bulk endpoint.

Registered before /{token_id} in routers/token.py -- these tests exist mainly to
guard against that route-ordering regression (a /{token_id}-shaped route
registered first would swallow "/tokens/bulk", treating "bulk" as an id).
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.token import Token


def _make_token(test_db, test_organization, user_id) -> Token:
    unique = uuid.uuid4().hex
    token = Token(
        name="Bulk-delete token",
        token=f"tok_{unique}",
        token_hash=unique,
        token_type="bearer",
        user_id=user_id,
        organization_id=test_organization.id,
    )
    test_db.add(token)
    test_db.flush()
    test_db.refresh(token)
    return token


class TestBulkDeleteTokensEndpoint:
    """Tests for DELETE /tokens/bulk"""

    def test_bulk_delete_returns_deleted_and_not_found_ids(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_organization,
        authenticated_user_id: str,
    ):
        token = _make_token(test_db, test_organization, authenticated_user_id)
        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/tokens/bulk",
            json={"token_ids": [str(token.id), fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [str(token.id)]
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
        token = _make_token(test_db, test_organization, authenticated_user_id)
        original_updated_at = token.updated_at
        test_db.commit()

        response = authenticated_client.request(
            "DELETE",
            "/tokens/bulk",
            json={"token_ids": [str(token.id)]},
        )
        assert response.status_code == status.HTTP_200_OK

        test_db.expire_all()
        with without_soft_delete_filter():
            deleted_token = test_db.query(Token).filter(Token.id == token.id).first()
        assert deleted_token is not None
        assert deleted_token.updated_at > original_updated_at

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request(
            "DELETE", "/tokens/bulk", json={"token_ids": [str(uuid.uuid4())]}
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
