"""Unit tests for POST /endpoints/{endpoint_id}/explore."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.organization_id = uuid.uuid4()
    return user


@pytest.fixture
def endpoint_id():
    return str(uuid.uuid4())


@pytest.fixture
def app(mock_user):
    from rhesis.backend.app.auth.user_utils import require_current_user_or_token
    from rhesis.backend.app.main import app as fastapi_app
    from rhesis.backend.app.utils.execution_validation import validate_generation_model

    fastapi_app.dependency_overrides[require_current_user_or_token] = lambda: mock_user
    fastapi_app.dependency_overrides[validate_generation_model] = lambda: None

    client = TestClient(fastapi_app, raise_server_exceptions=False)
    yield client
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestExploreEndpointHappy:
    def test_returns_task_id(self, app, endpoint_id, mock_user):
        mock_ep = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = str(uuid.uuid4())

        with (
            patch("rhesis.backend.app.routers.endpoint.crud") as mock_crud,
            patch("rhesis.backend.app.routers.endpoint.task_launcher", return_value=mock_async_result),
        ):
            mock_crud.get_endpoint.return_value = mock_ep

            response = app.post(
                f"/endpoints/{endpoint_id}/explore",
                json={"strategy": "domain_probing"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "task_id" in data
        assert "message" in data

    def test_goal_without_strategy_accepted(self, app, endpoint_id, mock_user):
        mock_ep = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = str(uuid.uuid4())

        with (
            patch("rhesis.backend.app.routers.endpoint.crud") as mock_crud,
            patch("rhesis.backend.app.routers.endpoint.task_launcher", return_value=mock_async_result),
        ):
            mock_crud.get_endpoint.return_value = mock_ep

            response = app.post(
                f"/endpoints/{endpoint_id}/explore",
                json={"goal": "Understand the endpoint's domain"},
            )

        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


class TestExploreEndpoint404:
    def test_returns_404_for_unknown_endpoint(self, app, endpoint_id):
        with patch("rhesis.backend.app.routers.endpoint.crud") as mock_crud:
            mock_crud.get_endpoint.return_value = None

            response = app.post(
                f"/endpoints/{endpoint_id}/explore",
                json={"strategy": "domain_probing"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 422 validation
# ---------------------------------------------------------------------------


class TestExploreEndpointValidation:
    def test_returns_422_when_neither_strategy_nor_goal(self, app, endpoint_id):
        response = app.post(
            f"/endpoints/{endpoint_id}/explore",
            json={"instructions": "some instructions only"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_returns_422_for_invalid_strategy(self, app, endpoint_id):
        response = app.post(
            f"/endpoints/{endpoint_id}/explore",
            json={"strategy": "not_a_real_strategy"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
