"""
Tests for the fields the task read endpoints return.

The task detail page shows "created on" from ``created_at``, which the Task
response schema used to leave out (along with ``updated_at``), so every task
read back as "created on: —".
"""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.models.task import Task


class TestTaskTimestamps:
    """``created_at`` and ``updated_at`` are returned by the detail and list endpoints."""

    def _task(self, test_db: Session, test_organization, user_id: str, status_id) -> Task:
        task = Task(
            title="Task with timestamps",
            user_id=user_id,
            organization_id=test_organization.id,
            status_id=status_id,
        )
        test_db.add(task)
        test_db.flush()
        test_db.refresh(task)
        return task

    def _assert_timestamps(self, row: dict, task: Task):
        assert row["created_at"] == task.created_at.isoformat()
        assert row["updated_at"] == task.updated_at.isoformat()

    def test_detail_returns_timestamps(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_organization,
        authenticated_user_id: str,
        db_status,
    ):
        task = self._task(test_db, test_organization, authenticated_user_id, db_status.id)

        response = authenticated_client.get(f"/tasks/{task.id}")

        assert response.status_code == status.HTTP_200_OK
        self._assert_timestamps(response.json(), task)

    def test_list_returns_timestamps(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_organization,
        authenticated_user_id: str,
        db_status,
    ):
        task = self._task(test_db, test_organization, authenticated_user_id, db_status.id)

        response = authenticated_client.get("/tasks/")

        assert response.status_code == status.HTTP_200_OK
        listed = {row["id"]: row for row in response.json()}
        self._assert_timestamps(listed[str(task.id)], task)
