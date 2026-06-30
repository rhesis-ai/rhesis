"""Unit tests for object-level authorization on task, test_result, and test_run routes.

Tests verify that non-creators receive HTTP 403 while the creator receives HTTP
200 for routes that are gated with ``authorize_object``:

- PATCH /tasks/{id}          — creator or assignee only
- DELETE /tasks/{id}         — creator only
- PUT  /test_results/{id}
- DELETE /test_results/{id}
- DELETE /test_runs/{id}

All SQLAlchemy query chains are mocked (no live database required), mirroring
the approach used in ``test_capabilities.py``.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.main import app

# ---------------------------------------------------------------------------
# Shared IDs
# ---------------------------------------------------------------------------

_ORG_ID = uuid.uuid4()
_CREATOR_ID = uuid.uuid4()
_OTHER_ID = uuid.uuid4()
_PROJECT_ID = uuid.uuid4()
_RESOURCE_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_mock(*, caller_id: uuid.UUID) -> Mock:
    """Mock db whose auth queries treat ``caller_id`` as a project member (not org owner)."""
    from rhesis.backend.app.models.organization import Organization
    from rhesis.backend.app.models.project_membership import ProjectMembership

    def _query_side_effect(model):
        q = Mock()
        if model is Organization:
            # Not org owner — forces project-membership path.
            q.filter_by.return_value.first.return_value = None
        elif model is ProjectMembership:
            # Always a project member so route-level cap passes.
            q.filter_by.return_value.first.return_value = Mock()
        else:
            q.filter_by.return_value.first.return_value = None
        return q

    db = Mock()
    db.query.side_effect = _query_side_effect
    db.info = {
        "_scope": SimpleNamespace(
            organization_id=str(_ORG_ID),
            user_id=str(caller_id),
            project_id=str(_PROJECT_ID),
        )
    }
    return db


def _make_user(user_id: uuid.UUID) -> Mock:
    user = Mock()
    user.id = user_id
    user.organization_id = _ORG_ID
    user.email = "test@example.com"
    user.name = "Test User"
    user.token_project_id = None
    user.token_scopes = None
    return user


def _client(*, caller_id: uuid.UUID) -> TestClient:
    """Build a TestClient with all deps overridden for ``caller_id``."""
    db = _make_db_mock(caller_id=caller_id)
    user = _make_user(caller_id)

    app.dependency_overrides[get_tenant_db_session] = lambda: db
    app.dependency_overrides[get_tenant_context] = lambda: (str(_ORG_ID), str(caller_id))
    app.dependency_overrides[require_current_user_or_token] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _db_test_result(*, owner_id: uuid.UUID) -> Mock:
    obj = Mock(spec_set=[
        "id", "user_id", "organization_id", "test_configuration_id",
        "test_run_id", "prompt_id", "test_id", "status_id",
        "test_metrics", "test_reviews", "test_output",
        "last_review", "matches_review", "review_summary",
        "permitted_actions",
    ])
    obj.id = _RESOURCE_ID
    obj.user_id = owner_id
    obj.organization_id = _ORG_ID
    obj.test_configuration_id = uuid.uuid4()
    obj.test_run_id = None
    obj.prompt_id = None
    obj.test_id = None
    obj.status_id = None
    obj.test_metrics = None
    obj.test_reviews = None
    obj.test_output = None
    obj.last_review = None
    obj.matches_review = False
    obj.review_summary = None
    obj.permitted_actions = []
    return obj


def _db_test_run(*, owner_id: uuid.UUID) -> Mock:
    obj = Mock(spec_set=[
        "id", "user_id", "organization_id", "test_configuration_id",
        "experiment_id", "status_id", "status", "name", "attributes",
        "owner_id", "assignee_id", "permitted_actions",
    ])
    obj.id = _RESOURCE_ID
    obj.user_id = owner_id
    obj.organization_id = _ORG_ID
    obj.test_configuration_id = uuid.uuid4()
    obj.experiment_id = None
    obj.status_id = None
    obj.status = None
    obj.name = "run"
    obj.attributes = {}
    obj.owner_id = None
    obj.assignee_id = None
    obj.permitted_actions = []
    return obj


def _db_task(*, owner_id: uuid.UUID, assignee_id: uuid.UUID | None = None) -> Mock:
    obj = Mock(spec_set=[
        "id", "user_id", "organization_id", "assignee_id",
        "title", "description", "status_id", "priority_id",
        "entity_type", "entity_id", "completed_at", "task_metadata",
        "comment_count", "user", "assignee", "status", "priority",
        "permitted_actions",
    ])
    obj.id = _RESOURCE_ID
    obj.user_id = owner_id
    obj.assignee_id = assignee_id
    obj.organization_id = _ORG_ID
    obj.title = "test task"
    obj.description = None
    obj.status_id = uuid.uuid4()  # required (UUID4, not Optional)
    obj.priority_id = None
    obj.entity_type = None
    obj.entity_id = None
    obj.completed_at = None
    obj.task_metadata = None
    obj.comment_count = 0
    obj.user = None
    obj.assignee = None
    obj.status = None
    obj.priority = None
    obj.permitted_actions = []
    return obj


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _register_caps():
    from rhesis.backend.app.auth.capabilities import register_capabilities

    register_capabilities(app)
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: PUT /test_results/{id}
# ---------------------------------------------------------------------------


class TestUpdateTestResultObjectAuth:
    def test_creator_can_update(self):
        result = _db_test_result(owner_id=_CREATOR_ID)
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.test_result.crud.get_test_result",
            return_value=result,
        ), patch(
            "rhesis.backend.app.routers.test_result.crud.update_test_result",
            return_value=result,
        ):
            resp = client.put(
                f"/test_results/{_RESOURCE_ID}",
                json={"test_configuration_id": str(uuid.uuid4())},
            )

        assert resp.status_code == status.HTTP_200_OK

    def test_non_creator_cannot_update(self):
        result = _db_test_result(owner_id=_CREATOR_ID)
        client = _client(caller_id=_OTHER_ID)

        with patch(
            "rhesis.backend.app.routers.test_result.crud.get_test_result",
            return_value=result,
        ):
            resp = client.put(
                f"/test_results/{_RESOURCE_ID}",
                json={"test_configuration_id": str(uuid.uuid4())},
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_result_returns_404(self):
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.test_result.crud.get_test_result",
            return_value=None,
        ):
            resp = client.put(
                f"/test_results/{_RESOURCE_ID}",
                json={"test_configuration_id": str(uuid.uuid4())},
            )

        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: DELETE /test_results/{id}
# ---------------------------------------------------------------------------


class TestDeleteTestResultObjectAuth:
    def test_creator_can_delete(self):
        result = _db_test_result(owner_id=_CREATOR_ID)
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.test_result.crud.get_test_result",
            return_value=result,
        ), patch(
            "rhesis.backend.app.routers.test_result.crud.delete_test_result",
            return_value=result,
        ):
            resp = client.delete(f"/test_results/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_200_OK

    def test_non_creator_cannot_delete(self):
        result = _db_test_result(owner_id=_CREATOR_ID)
        client = _client(caller_id=_OTHER_ID)

        with patch(
            "rhesis.backend.app.routers.test_result.crud.get_test_result",
            return_value=result,
        ):
            resp = client.delete(f"/test_results/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_result_returns_404(self):
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.test_result.crud.get_test_result",
            return_value=None,
        ):
            resp = client.delete(f"/test_results/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: DELETE /test_runs/{id}
# ---------------------------------------------------------------------------


class TestDeleteTestRunObjectAuth:
    def test_creator_can_delete(self):
        run = _db_test_run(owner_id=_CREATOR_ID)
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.test_run.crud.get_test_run",
            return_value=run,
        ), patch(
            "rhesis.backend.app.routers.test_run.crud.delete_test_run",
            return_value=run,
        ):
            resp = client.delete(f"/test_runs/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_200_OK

    def test_non_creator_cannot_delete(self):
        run = _db_test_run(owner_id=_CREATOR_ID)
        client = _client(caller_id=_OTHER_ID)

        with patch(
            "rhesis.backend.app.routers.test_run.crud.get_test_run",
            return_value=run,
        ):
            resp = client.delete(f"/test_runs/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_run_returns_404(self):
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.test_run.crud.get_test_run",
            return_value=None,
        ):
            resp = client.delete(f"/test_runs/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: PATCH /tasks/{id}  — creator OR assignee may update
# ---------------------------------------------------------------------------

_ASSIGNEE_ID = uuid.uuid4()


class TestUpdateTaskObjectAuth:
    def test_creator_can_update(self):
        task = _db_task(owner_id=_CREATOR_ID)
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=task,
        ), patch(
            "rhesis.backend.app.routers.task_management.crud.update_task",
            return_value=task,
        ), patch(
            "rhesis.backend.app.routers.task_management.validate_task_organization_constraints",
        ):
            resp = client.patch(f"/tasks/{_RESOURCE_ID}", json={"title": "updated"})

        assert resp.status_code == status.HTTP_200_OK

    def test_assignee_can_update(self):
        task = _db_task(owner_id=_CREATOR_ID, assignee_id=_ASSIGNEE_ID)
        client = _client(caller_id=_ASSIGNEE_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=task,
        ), patch(
            "rhesis.backend.app.routers.task_management.crud.update_task",
            return_value=task,
        ), patch(
            "rhesis.backend.app.routers.task_management.validate_task_organization_constraints",
        ):
            resp = client.patch(f"/tasks/{_RESOURCE_ID}", json={"title": "updated"})

        assert resp.status_code == status.HTTP_200_OK

    def test_unrelated_member_cannot_update(self):
        """A project member who is neither creator nor assignee must be denied."""
        task = _db_task(owner_id=_CREATOR_ID, assignee_id=_ASSIGNEE_ID)
        client = _client(caller_id=_OTHER_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=task,
        ):
            resp = client.patch(f"/tasks/{_RESOURCE_ID}", json={"title": "updated"})

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_task_returns_404(self):
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=None,
        ):
            resp = client.patch(f"/tasks/{_RESOURCE_ID}", json={"title": "updated"})

        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: DELETE /tasks/{id}  — creator only
# ---------------------------------------------------------------------------


class TestDeleteTaskObjectAuth:
    def test_creator_can_delete(self):
        task = _db_task(owner_id=_CREATOR_ID)
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=task,
        ), patch(
            "rhesis.backend.app.routers.task_management.crud.delete_task",
            return_value=True,
        ):
            resp = client.delete(f"/tasks/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_200_OK

    def test_assignee_cannot_delete(self):
        """Being the assignee does NOT grant delete rights."""
        task = _db_task(owner_id=_CREATOR_ID, assignee_id=_ASSIGNEE_ID)
        client = _client(caller_id=_ASSIGNEE_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=task,
        ):
            resp = client.delete(f"/tasks/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unrelated_member_cannot_delete(self):
        task = _db_task(owner_id=_CREATOR_ID)
        client = _client(caller_id=_OTHER_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=task,
        ):
            resp = client.delete(f"/tasks/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_task_returns_404(self):
        client = _client(caller_id=_CREATOR_ID)

        with patch(
            "rhesis.backend.app.routers.task_management.crud.get_task",
            return_value=None,
        ):
            resp = client.delete(f"/tasks/{_RESOURCE_ID}")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
