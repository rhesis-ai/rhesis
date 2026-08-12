"""Tests for services.task_notification.send_task_assignment_in_app_notification().

The email counterpart (send_task_assignment_notification) has no existing test
file; this covers only the new in-app path.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.notification import get_notifications
from rhesis.backend.app.services.task_notification import (
    send_task_assignment_in_app_notification,
)
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from tests.backend.fixtures.test_setup import create_test_user


@pytest.mark.integration
class TestSendTaskAssignmentInAppNotification:
    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session, test_org_id, authenticated_user_id):
        self.db = test_db
        self.org_id = test_org_id
        self.creator_id = authenticated_user_id
        self.assignee = create_test_user(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            email=f"assignee-{uuid.uuid4().hex[:8]}@rhesis-test.com",
            name="Assignee User",
        )
        self.status = get_or_create_status(
            db=test_db,
            name="Open",
            entity_type="Task",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

    def _make_task(self, *, assignee_id=None, title="Do the thing"):
        task = models.Task(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(self.org_id),
            user_id=uuid.UUID(self.creator_id),
            assignee_id=assignee_id,
            title=title,
            status_id=self.status.id,
        )
        self.db.add(task)
        self.db.commit()
        return task

    def test_creates_notification_for_the_assignee(self):
        task = self._make_task(assignee_id=self.assignee.id)

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            send_task_assignment_in_app_notification(self.db, task)

        rows = get_notifications(self.db, user_id=str(self.assignee.id))
        assert len(rows) == 1
        row = rows[0]
        assert row.section == "tasks"
        assert row.event_type == "task.assigned"
        assert row.entity_id == task.id
        assert row.title == '"Do the thing" was assigned to you'

    def test_does_not_notify_the_creator(self):
        task = self._make_task(assignee_id=self.assignee.id)

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            send_task_assignment_in_app_notification(self.db, task)

        creator_rows = get_notifications(self.db, user_id=self.creator_id)
        assert creator_rows == []

    def test_body_names_the_creator(self, test_db):
        creator = (
            test_db.query(models.User).filter(models.User.id == uuid.UUID(self.creator_id)).one()
        )
        task = self._make_task(assignee_id=self.assignee.id)

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            send_task_assignment_in_app_notification(self.db, task)

        rows = get_notifications(self.db, user_id=str(self.assignee.id))
        expected_name = creator.name or creator.given_name
        assert rows[0].body == f"Assigned by {expected_name}"

    def test_noop_without_an_assignee(self):
        task = self._make_task(assignee_id=None)

        with patch(
            "rhesis.backend.app.services.notification.service.publish_event"
        ) as mock_publish:
            send_task_assignment_in_app_notification(self.db, task)

        mock_publish.assert_not_called()
        assert get_notifications(self.db, user_id=self.creator_id) == []
