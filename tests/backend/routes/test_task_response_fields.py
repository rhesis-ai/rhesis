"""
Tests for the fields the task read endpoints return.

The task detail page shows "created on" from ``created_at``, which the Task
response schema used to leave out, so every task read back as "created on: —".
"""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.models.task import Task


class TestTaskCreatedAt:
    """``created_at`` is returned by the task detail and list endpoints."""

    def _task(self, test_db: Session, test_organization, user_id: str, status_id) -> Task:
        task = Task(
            title="Task with a creation time",
            user_id=user_id,
            organization_id=test_organization.id,
            status_id=status_id,
        )
        test_db.add(task)
        test_db.flush()
        test_db.refresh(task)
        return task

    def test_detail_returns_created_at(
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
        assert response.json()["created_at"] == task.created_at.isoformat()

    def test_list_returns_created_at(
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
        assert listed[str(task.id)]["created_at"] == task.created_at.isoformat()
