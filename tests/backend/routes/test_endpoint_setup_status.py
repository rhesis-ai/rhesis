"""GET /endpoints/setup-status: per project, seeded example endpoints don't count.

``create_test_organization_and_user`` runs ``load_initial_data``, so every org here
starts with the example project and its example endpoint -- the day-one state.
"""

import uuid
from contextlib import contextmanager

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.enums import NotificationEventType, NotificationSection
from rhesis.backend.app.models.notification import Notification
from rhesis.backend.app.scope import RequestScope
from rhesis.backend.app.services.organization import EXAMPLE_PROJECT_NAME
from tests.backend.fixtures.rls import as_project
from tests.backend.fixtures.test_setup import create_test_organization_and_user

SETUP_STATUS_URL = "/endpoints/setup-status"


@pytest.fixture
def seeded_owner(test_db: Session, client):
    """A client signed in as the owner of a freshly seeded organization."""
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"Setup Status Org {suffix}",
        f"setup_status_{suffix}@rhesis-test.com",
        "Setup Status Owner",
    )
    client.headers.update({"Authorization": f"Bearer {token.token}"})
    return client, str(org.id), str(user.id)


def _example_project(db: Session, org_id: str) -> models.Project:
    return (
        db.query(models.Project)
        .filter(
            models.Project.organization_id == org_id,
            models.Project.name == EXAMPLE_PROJECT_NAME,
        )
        .one()
    )


def _add_project(db: Session, org_id: str, user_id: str) -> models.Project:
    project = models.Project(
        name=f"Own Project {uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        user_id=user_id,
        owner_id=user_id,
    )
    db.add(project)
    db.flush()
    return project


def _add_endpoint(db: Session, org_id: str, user_id: str, project_id) -> None:
    with as_project(db, project_id):
        db.add(
            models.Endpoint(
                name="Own Endpoint",
                connection_type="REST",
                organization_id=org_id,
                user_id=user_id,
                project_id=project_id,
            )
        )
        db.flush()


def _nudges(db: Session, user_id: str, project_id) -> list[Notification]:
    with as_project(db, project_id):
        return (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.project_id == project_id,
                Notification.event_type == NotificationEventType.Endpoint.SETUP_REQUIRED.value,
            )
            .all()
        )


@contextmanager
def _in_project(db: Session, org_id: str, user_id: str, project_id):
    """What X-Project-Id gives a real request: the RLS setting plus the session scope.

    Route tests bypass the real get_tenant_db_session, so both are set by hand.
    """
    previous = db.info.get("_scope")
    db.info["_scope"] = RequestScope(
        organization_id=org_id,
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    try:
        with as_project(db, project_id):
            yield
    finally:
        if previous is None:
            db.info.pop("_scope", None)
        else:
            db.info["_scope"] = previous


def _get(client, db: Session, org_id: str, user_id: str, project_id):
    with _in_project(db, org_id, user_id, project_id):
        response = client.get(SETUP_STATUS_URL)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


@pytest.mark.unit
class TestEndpointSetupStatus:
    def test_example_endpoint_does_not_count(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        example = _example_project(test_db, org_id)

        assert _get(client, test_db, org_id, user_id, example.id) == {"configured": False}

    def test_own_endpoint_counts(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        example = _example_project(test_db, org_id)
        _add_endpoint(test_db, org_id, user_id, example.id)

        assert _get(client, test_db, org_id, user_id, example.id) == {"configured": True}
        assert _nudges(test_db, user_id, example.id) == []

    def test_status_is_per_project(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        with_endpoint = _add_project(test_db, org_id, user_id)
        without_endpoint = _add_project(test_db, org_id, user_id)
        _add_endpoint(test_db, org_id, user_id, with_endpoint.id)

        assert _get(client, test_db, org_id, user_id, with_endpoint.id) == {"configured": True}
        assert _get(client, test_db, org_id, user_id, without_endpoint.id) == {"configured": False}

    def test_endpoint_created_as_example_does_not_count(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        example = _example_project(test_db, org_id)
        with _in_project(test_db, org_id, user_id, example.id):
            created = client.post(
                "/endpoints/",
                json={
                    "name": "Local Mock Chatbot",
                    "connection_type": "REST",
                    "url": "http://localhost:18090",
                    "project_id": str(example.id),
                    "is_example": True,
                },
            )
        assert created.status_code == status.HTTP_200_OK, created.text

        assert _get(client, test_db, org_id, user_id, example.id) == {"configured": False}

    def test_no_project_is_unknown_and_sends_nothing(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner

        assert _get(client, test_db, org_id, user_id, None) == {"configured": None}
        assert (
            test_db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.event_type == NotificationEventType.Endpoint.SETUP_REQUIRED.value,
            )
            .count()
            == 0
        )


@pytest.mark.unit
class TestEndpointSetupNotification:
    def test_not_sent_in_the_example_project(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        example = _example_project(test_db, org_id)

        assert _get(client, test_db, org_id, user_id, example.id) == {"configured": False}
        assert _nudges(test_db, user_id, example.id) == []

    def test_sent_once_per_project(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        project = _add_project(test_db, org_id, user_id)

        _get(client, test_db, org_id, user_id, project.id)
        _get(client, test_db, org_id, user_id, project.id)

        [nudge] = _nudges(test_db, user_id, project.id)
        assert nudge.section == NotificationSection.ENDPOINTS.value
        assert nudge.read_at is None

    def test_each_project_gets_its_own(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        first = _add_project(test_db, org_id, user_id)
        second = _add_project(test_db, org_id, user_id)

        _get(client, test_db, org_id, user_id, first.id)
        _get(client, test_db, org_id, user_id, second.id)

        assert len(_nudges(test_db, user_id, first.id)) == 1
        assert len(_nudges(test_db, user_id, second.id)) == 1
