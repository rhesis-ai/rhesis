"""Tests for POST /tests/bulk error statuses.

The endpoint raises its own 400 inside the same `try` that has a broad
`except Exception`. Without an `except HTTPException: raise` arm above that
handler, the 400 is caught and re-raised as a 500 -- a client error reported
as a server error, with the reason stripped.
"""

from fastapi import status
from fastapi.testclient import TestClient


class TestBulkCreateTestsErrors:
    def test_empty_test_list_returns_400_not_500(self, authenticated_client: TestClient):
        response = authenticated_client.post("/tests/bulk", json={"tests": []})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "No tests provided in request"
