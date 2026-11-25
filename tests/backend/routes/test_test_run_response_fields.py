"""
Tests for the timestamps the test run read endpoints return.

The Test Runs grid shows a "Created" column from ``created_at``, which the
TestRun response schema used to leave out (along with ``updated_at``), so
every run showed "N/A".
"""

from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.models.test_run import TestRun


def _assert_timestamps(row: dict, test_run: TestRun):
    assert row["created_at"] == test_run.created_at.isoformat()
    assert row["updated_at"] == test_run.updated_at.isoformat()


class TestTestRunTimestamps:
    """``created_at`` and ``updated_at`` are returned by the detail and list endpoints."""

    def test_detail_returns_timestamps(
        self, authenticated_client: TestClient, db_test_run: TestRun
    ):
        response = authenticated_client.get(f"/test_runs/{db_test_run.id}")

        assert response.status_code == status.HTTP_200_OK
        _assert_timestamps(response.json(), db_test_run)

    def test_list_returns_timestamps(self, authenticated_client: TestClient, db_test_run: TestRun):
        response = authenticated_client.get("/test_runs/")

        assert response.status_code == status.HTTP_200_OK
        listed = {row["id"]: row for row in response.json()}
        _assert_timestamps(listed[str(db_test_run.id)], db_test_run)
