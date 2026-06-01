"""
Tests for GET /tests/{test_id}/test_sets endpoint.

Tests the endpoint that returns all test sets a given test belongs to.
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient


class TestGetTestTestSets:
    """Tests for GET /tests/{test_id}/test_sets"""

    def test_returns_empty_list_when_no_test_sets(
        self, authenticated_client: TestClient, db_test
    ):
        """Returns an empty list when the test has no linked test sets."""
        response = authenticated_client.get(f"/tests/{db_test.id}/test_sets")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []
        assert response.headers.get("X-Total-Count") == "0"

    def test_returns_linked_test_sets(
        self, authenticated_client: TestClient, db_test_set_with_tests
    ):
        """Returns the test sets that a test belongs to."""
        test_set = db_test_set_with_tests
        test_id = test_set.tests[0].id

        response = authenticated_client.get(f"/tests/{test_id}/test_sets")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        ids = [item["id"] for item in data]
        assert str(test_set.id) in ids
        assert int(response.headers.get("X-Total-Count", 0)) >= 1

    def test_returns_404_for_nonexistent_test(self, authenticated_client: TestClient):
        """Returns 404 when the test does not exist."""
        fake_id = str(uuid.uuid4())
        response = authenticated_client.get(f"/tests/{fake_id}/test_sets")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_pagination_limit(
        self, authenticated_client: TestClient, db_test_set_with_tests
    ):
        """Pagination limit parameter is respected."""
        test_id = db_test_set_with_tests.tests[0].id
        response = authenticated_client.get(
            f"/tests/{test_id}/test_sets?skip=0&limit=1"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 1

    def test_requires_authentication(self, client: TestClient, db_test):
        """Unauthenticated requests are rejected."""
        response = client.get(f"/tests/{db_test.id}/test_sets")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
