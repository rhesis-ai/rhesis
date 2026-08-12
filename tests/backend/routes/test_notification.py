"""Router tests for /notifications: summary, list, mark-read.

The security-relevant case covered here: a user must never see another
user's notifications in the same org (the ambient auto-filter scopes by
org/project only, not by user -- see crud/notification.py).

Project-scoping (a notification hidden once a different project is active)
is covered at the CRUD level instead, in
tests/backend/services/notification/test_service.py -- the `client`/`test_db`
fixture overrides `get_tenant_db_session` with a no-op yielding the shared
session, so an `X-Project-Id` request header here never reaches the real
per-request scope-binding dependency it would in production.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.crud.notification import create_notification
from rhesis.backend.app.models.enums import NotificationEventType, NotificationSection
from tests.backend.fixtures.test_setup import create_test_user


@pytest.fixture
def other_user(test_db: Session, test_org_id):
    """A second real user in the same org, for cross-user isolation tests."""
    return create_test_user(
        test_db,
        organization_id=uuid.UUID(test_org_id),
        email=f"other-{uuid.uuid4().hex[:8]}@rhesis-test.com",
        name="Other User",
    )


def _make_notification(db, *, user_id, organization_id, project_id=None, section=None, title="t"):
    return create_notification(
        db,
        event_type=NotificationEventType.TestSet.GENERATION_COMPLETED,
        section=section or NotificationSection.TEST_SETS.value,
        title=title,
        user_id=user_id,
        organization_id=organization_id,
        project_id=project_id,
    )


@pytest.mark.integration
class TestNotificationSummary:
    def test_empty_initially(self, authenticated_client: TestClient):
        response = authenticated_client.get("/notifications/summary")
        assert response.status_code == 200
        assert response.json()["sections"] == {}

    def test_counts_own_unread_notification(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        _make_notification(test_db, user_id=authenticated_user_id, organization_id=test_org_id)

        response = authenticated_client.get("/notifications/summary")
        assert response.status_code == 200
        sections = response.json()["sections"]
        assert sections["test-sets"]["unread"] == 1

    def test_excludes_other_users_notifications(
        self,
        authenticated_client: TestClient,
        test_db,
        test_org_id,
        other_user,
    ):
        _make_notification(test_db, user_id=str(other_user.id), organization_id=test_org_id)

        response = authenticated_client.get("/notifications/summary")
        assert response.status_code == 200
        assert response.json()["sections"] == {}

    def test_counts_are_exact_beyond_the_highlight_scan_limit(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Counts come from a SQL aggregate, so the bounded highlight scan
        (``_SUMMARY_HIGHLIGHT_SCAN_LIMIT``) must not cap them."""
        from rhesis.backend.app.crud import notification as notification_crud

        over_limit = notification_crud._SUMMARY_HIGHLIGHT_SCAN_LIMIT + 5
        for _ in range(over_limit):
            _make_notification(test_db, user_id=authenticated_user_id, organization_id=test_org_id)

        response = authenticated_client.get("/notifications/summary")
        assert response.status_code == 200
        assert response.json()["sections"]["test-sets"]["unread"] == over_limit


@pytest.mark.integration
class TestMarkRead:
    def test_marks_only_the_requested_section(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        _make_notification(
            test_db,
            user_id=authenticated_user_id,
            organization_id=test_org_id,
            section=NotificationSection.TEST_SETS.value,
        )
        _make_notification(
            test_db,
            user_id=authenticated_user_id,
            organization_id=test_org_id,
            section=NotificationSection.TEST_RUNS.value,
        )

        response = authenticated_client.post("/notifications/read", json={"section": "test-sets"})
        assert response.status_code == 200
        assert response.json()["updated"] == 1

        summary = authenticated_client.get("/notifications/summary").json()["sections"]
        assert "test-sets" not in summary
        assert summary["test-runs"]["unread"] == 1

    def test_marks_specific_ids(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        keep = _make_notification(
            test_db, user_id=authenticated_user_id, organization_id=test_org_id, title="keep"
        )
        clear = _make_notification(
            test_db, user_id=authenticated_user_id, organization_id=test_org_id, title="clear"
        )

        response = authenticated_client.post(
            "/notifications/read", json={"notification_ids": [str(clear.id)]}
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 1

        summary = authenticated_client.get("/notifications/summary").json()["sections"]
        assert summary["test-sets"]["unread"] == 1
        test_db.refresh(keep)
        assert keep.read_at is None

    def test_section_and_ids_narrow_together(
        self, authenticated_client: TestClient, test_db, test_org_id, authenticated_user_id
    ):
        """Passing both must never mark more than either filter alone would.

        The id below is in test-sets, so scoping to test-runs matches nothing --
        an OR would have wrongly cleared the whole test-runs section too.
        """
        in_test_sets = _make_notification(
            test_db,
            user_id=authenticated_user_id,
            organization_id=test_org_id,
            section=NotificationSection.TEST_SETS.value,
        )
        _make_notification(
            test_db,
            user_id=authenticated_user_id,
            organization_id=test_org_id,
            section=NotificationSection.TEST_RUNS.value,
        )

        response = authenticated_client.post(
            "/notifications/read",
            json={"section": "test-runs", "notification_ids": [str(in_test_sets.id)]},
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 0

        summary = authenticated_client.get("/notifications/summary").json()["sections"]
        assert summary["test-sets"]["unread"] == 1
        assert summary["test-runs"]["unread"] == 1

    def test_requires_section_or_ids(self, authenticated_client: TestClient):
        response = authenticated_client.post("/notifications/read", json={})
        assert response.status_code == 400
