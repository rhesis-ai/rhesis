"""Tests for services.notification.notify().

Covers: row creation, the websocket publish call (target + payload shape),
and that a publish failure never propagates -- a Celery task's on_success
must not fail because Redis is down.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.notification import get_notification_summary, get_notifications
from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.app.schemas.websocket import EventType, UserTarget
from rhesis.backend.app.services.notification.catalog import RenderedNotification
from rhesis.backend.app.services.notification.service import notify


@pytest.mark.integration
class TestNotify:
    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session, test_org_id, authenticated_user_id):
        self.db = test_db
        self.org_id = test_org_id
        self.user_id = authenticated_user_id

    def test_creates_notification_row(self):
        rendered = RenderedNotification(title='"my set" is ready', body="10 tests generated")

        with patch(
            "rhesis.backend.app.services.notification.service.publish_event"
        ) as mock_publish:
            notify(
                self.db,
                event_type=NotificationEventType.TestSet.GENERATION_COMPLETED,
                rendered=rendered,
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=None,
            )

        rows = get_notifications(self.db, user_id=self.user_id)
        assert any(r.title == '"my set" is ready' for r in rows)
        mock_publish.assert_called_once()

    def test_publishes_to_recipient_user_target(self):
        rendered = RenderedNotification(title="Test run finished", entity_id=None)

        with patch(
            "rhesis.backend.app.services.notification.service.publish_event"
        ) as mock_publish:
            notify(
                self.db,
                event_type=NotificationEventType.TestRun.EXECUTION_COMPLETED,
                rendered=rendered,
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=None,
            )

        message, target = mock_publish.call_args[0]
        assert isinstance(target, UserTarget)
        assert target.user_id == str(self.user_id)
        assert message.type == EventType.NOTIFICATION
        assert message.payload["title"] == "Test run finished"
        assert message.payload["section"] == "test-runs"

    def test_publish_failure_does_not_raise(self):
        rendered = RenderedNotification(title="Garak sync complete")

        with patch(
            "rhesis.backend.app.services.notification.service.publish_event",
            side_effect=RuntimeError("redis is down"),
        ):
            # Must not raise -- a broker/Redis failure must not fail the caller.
            notify(
                self.db,
                event_type=NotificationEventType.TestSet.GARAK_SYNC_COMPLETED,
                rendered=rendered,
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=None,
            )

        rows = get_notifications(self.db, user_id=self.user_id)
        assert any(r.title == "Garak sync complete" for r in rows)

    def test_batch_notification_counts_as_its_entities(self):
        """One Garak import that made three test sets must badge as three."""
        entity_ids = [str(uuid.uuid4()) for _ in range(3)]
        rendered = RenderedNotification(title="Imported 3 Garak test set(s)", entity_ids=entity_ids)

        with patch(
            "rhesis.backend.app.services.notification.service.publish_event"
        ) as mock_publish:
            notify(
                self.db,
                event_type=NotificationEventType.TestSet.GARAK_IMPORT_COMPLETED,
                rendered=rendered,
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=None,
            )

        rows = get_notifications(self.db, user_id=self.user_id)
        row = next(r for r in rows if r.title == "Imported 3 Garak test set(s)")
        assert row.item_count == 3
        assert row.payload["entity_ids"] == entity_ids

        # The frontend badges straight off the websocket payload, so the count
        # has to be on the wire too, not only in the summary endpoint.
        message, _target = mock_publish.call_args[0]
        assert message.payload["item_count"] == 3

    def test_single_entity_notification_counts_as_one(self):
        rendered = RenderedNotification(title="single", entity_id=str(uuid.uuid4()))

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify(
                self.db,
                event_type=NotificationEventType.TestSet.GENERATION_COMPLETED,
                rendered=rendered,
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=None,
            )

        rows = get_notifications(self.db, user_id=self.user_id)
        assert next(r for r in rows if r.title == "single").item_count == 1

    def test_summary_sums_item_counts_across_rows(self):
        """Two batches of three, plus one single, is seven -- not three rows."""
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            for _ in range(2):
                notify(
                    self.db,
                    event_type=NotificationEventType.TestSet.GARAK_IMPORT_COMPLETED,
                    rendered=RenderedNotification(
                        title="batch", entity_ids=[str(uuid.uuid4()) for _ in range(3)]
                    ),
                    user_id=self.user_id,
                    organization_id=self.org_id,
                    project_id=None,
                )
            notify(
                self.db,
                event_type=NotificationEventType.TestSet.GENERATION_COMPLETED,
                rendered=RenderedNotification(title="single", entity_id=str(uuid.uuid4())),
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=None,
            )

        summary = get_notification_summary(self.db, user_id=self.user_id)
        assert summary["test-sets"]["unread"] == 7
        assert len(summary["test-sets"]["entity_ids"]) == 7

    # Keep this name off 40 characters. `test_` plus exactly 35 more is the
    # shape of a Lob test-mode API key, and the repo's TruffleHog job flags
    # such a name as a verified secret and fails the build.
    def test_summary_entity_ids_are_deduped(self):
        """The same test set synced twice is one row to highlight, not two."""
        entity_id = str(uuid.uuid4())
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            for _ in range(2):
                notify(
                    self.db,
                    event_type=NotificationEventType.TestSet.GARAK_SYNC_COMPLETED,
                    rendered=RenderedNotification(title="synced", entity_id=entity_id),
                    user_id=self.user_id,
                    organization_id=self.org_id,
                    project_id=None,
                )

        summary = get_notification_summary(self.db, user_id=self.user_id)
        assert summary["test-sets"]["unread"] == 2
        assert summary["test-sets"]["entity_ids"] == [entity_id]

    def test_failure_notification_is_flagged(self):
        rendered = RenderedNotification(title="Test set generation failed", is_failure=True)

        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify(
                self.db,
                event_type=NotificationEventType.TestSet.GENERATION_COMPLETED,
                rendered=rendered,
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=None,
            )

        rows = get_notifications(self.db, user_id=self.user_id)
        row = next(r for r in rows if r.title == "Test set generation failed")
        assert row.is_failure is True


@pytest.mark.integration
class TestNotificationProjectScoping:
    """A notification created for project A must not count toward the badge
    while a different project is active, per the ambient auto-filter (see
    `apps/backend/AGENTS.md`'s "Ambient Request Scope").

    `notify()`/`create_notification()` don't apply the auto-filter themselves
    (writes always succeed); this exercises the *read* side
    (`get_notification_summary`) under `bound_scope`, since the `client`
    fixture's DI override means an `X-Project-Id` header can't reach the real
    per-request scope-binding dependency in a router-level test.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session, test_org_id, authenticated_user_id):
        self.db = test_db
        self.org_id = test_org_id
        self.user_id = authenticated_user_id
        self.project_a = models.Project(
            name=f"Project A {uuid.uuid4().hex[:8]}", organization_id=uuid.UUID(test_org_id)
        )
        self.project_b = models.Project(
            name=f"Project B {uuid.uuid4().hex[:8]}", organization_id=uuid.UUID(test_org_id)
        )
        self.db.add_all([self.project_a, self.project_b])
        self.db.flush()

    def _notify(self, project_id):
        with patch("rhesis.backend.app.services.notification.service.publish_event"):
            notify(
                self.db,
                event_type=NotificationEventType.TestSet.GENERATION_COMPLETED,
                rendered=RenderedNotification(title="scoped"),
                user_id=self.user_id,
                organization_id=self.org_id,
                project_id=project_id,
            )

    def test_hidden_while_a_different_project_is_active(self, bound_scope):
        self._notify(str(self.project_a.id))

        with bound_scope(
            organization_id=self.org_id, user_id=self.user_id, project_id=str(self.project_b.id)
        ):
            summary = get_notification_summary(self.db, user_id=self.user_id)

        assert summary == {}

    def test_visible_in_its_own_project(self, bound_scope):
        self._notify(str(self.project_a.id))

        with bound_scope(
            organization_id=self.org_id, user_id=self.user_id, project_id=str(self.project_a.id)
        ):
            summary = get_notification_summary(self.db, user_id=self.user_id)

        assert summary["test-sets"]["unread"] == 1

    def test_org_wide_notification_visible_regardless_of_active_project(self, bound_scope):
        self._notify(None)

        with bound_scope(
            organization_id=self.org_id, user_id=self.user_id, project_id=str(self.project_b.id)
        ):
            summary = get_notification_summary(self.db, user_id=self.user_id)

        assert summary["test-sets"]["unread"] == 1
