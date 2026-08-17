"""
Regression coverage for the test set soft-delete contract.

A soft-deleted test set must surface 410 GONE on every route that resolves it by
identifier -- not just GET, but also routes wrapped in their own try/except
(download) or routed through handle_execution_error (execute) -- since either
could otherwise swallow ItemDeletedException into a bare 500.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestTestSetSoftDeleteContract:
    def test_get_deleted_test_set_returns_410(self, authenticated_client: TestClient, db_test_set):
        test_set_id = db_test_set.id

        delete_response = authenticated_client.delete(f"/test_sets/{test_set_id}")
        assert delete_response.status_code == status.HTTP_200_OK

        response = authenticated_client.get(f"/test_sets/{test_set_id}")
        assert response.status_code == status.HTTP_410_GONE

    def test_download_deleted_test_set_returns_410(
        self, authenticated_client: TestClient, db_test_set
    ):
        test_set_id = db_test_set.id

        delete_response = authenticated_client.delete(f"/test_sets/{test_set_id}")
        assert delete_response.status_code == status.HTTP_200_OK

        response = authenticated_client.get(f"/test_sets/{test_set_id}/download")
        assert response.status_code == status.HTTP_410_GONE
