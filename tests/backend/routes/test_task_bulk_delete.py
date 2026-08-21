"""
Tests for DELETE /tasks/bulk endpoint.

Registered before /{task_id} in routers/task_management.py -- these tests guard
against that route-ordering regression, and against the owner-only delete
rule (only the creator may delete a task) being silently dropped for the
bulk path the way a naive bulk_delete_by_ids() call would: Task has no
visibility column, so without the owner_attr filter any org member could
bulk-delete anyone's tasks.
"""

import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.task import Task


class TestBulkDeleteTasksEndpoint:
    """Tests for DELETE /tasks/bulk"""

    def test_bulk_delete_buckets_owned_forbidden_and_not_found_ids(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_organization,
        authenticated_user_id: str,
        db_status,
        db_user,
    ):
        """One id owned by the caller, one owned by someone else (same org),
        and one that doesn't exist -- each must land in exactly one bucket.
        ``db_user`` is a different user than the caller, so a task created
        for them doubles as the "forbidden" case here.
        """
        owned_task = Task(
            title="Caller's task",
            user_id=authenticated_user_id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        foreign_task = Task(
            title="Someone else's task",
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add_all([owned_task, foreign_task])
        test_db.flush()
        test_db.refresh(owned_task)
        test_db.refresh(foreign_task)

        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/tasks/bulk",
            json={"task_ids": [str(owned_task.id), str(foreign_task.id), fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [str(owned_task.id)]
        assert data["forbidden_ids"] == [str(foreign_task.id)]
        assert data["not_found_ids"] == [fake_id]

        test_db.expire_all()
        with without_soft_delete_filter():
            still_present = test_db.query(Task).filter(Task.id == foreign_task.id).first()
        # Forbidden id must not be deleted, unlike not_found ids which never existed.
        assert still_present is not None
        assert still_present.deleted_at is None

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request(
            "DELETE", "/tasks/bulk", json={"task_ids": [str(uuid.uuid4())]}
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
