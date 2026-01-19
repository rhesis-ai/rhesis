from enum import Enum
from typing import ClassVar, Optional
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from rhesis.sdk.client import HTTPStatus
from rhesis.sdk.entities.base_entity import BaseEntity
from tests.sdk.conftest import RHESIS_API_KEY, RHESIS_BASE_URL


class TestEndpoint(Enum):
    __test__ = False
    TEST = "test"


class TestEntity(BaseEntity):
    __test__ = False
    endpoint: ClassVar[TestEndpoint] = TestEndpoint.TEST

    name: str
    description: str
    id: Optional[int] = None


@pytest.fixture
def test_entity():
    return TestEntity(name="Test", description="Test", id=1)


@pytest.fixture
def test_entity_without_id():
    return TestEntity(name="Test", description="Test", id=None)


@patch("requests.request")
def test_delete_by_id(mock_request, test_entity):
    record_id = 1
    test_entity = test_entity
    test_entity._delete(record_id)
    mock_request.assert_called_once_with(
        method="DELETE",
        url=f"{RHESIS_BASE_URL}/test/1",
        headers={
            "Authorization": f"Bearer {RHESIS_API_KEY}",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )

    # Mock not found error response
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.NOT_FOUND

    http_error = HTTPError("404 Not Found")
    http_error.response = mock_response
    mock_request.side_effect = http_error

    record_id = 1
    entity = TestEntity(name="Test", description="Test", id=1)
    result = entity._delete(record_id)
    assert result is False


@patch("requests.request")
def test_push_with_id(mock_request, test_entity):
    test_entity.push()
    mock_request.assert_called_once_with(
        method="PUT",
        url=f"{RHESIS_BASE_URL}/test/1",
        headers={
            "Authorization": f"Bearer {RHESIS_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"name": "Test", "description": "Test", "id": 1},
        params=None,
    )


@patch("requests.request")
def test_push_without_id(mock_request, test_entity_without_id):
    test_entity_without_id.push()
    mock_request.assert_called_once_with(
        method="POST",
        url=f"{RHESIS_BASE_URL}/test",
        headers={
            "Authorization": f"Bearer {RHESIS_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"name": "Test", "description": "Test", "id": None},
        params=None,
    )


@patch("requests.request")
def test_pull_by_id(mock_request, test_entity):
    mock_request.return_value.json.return_value = {
        "id": 1,
        "name": "Test",
        "description": "Test",
    }
    test_entity._pull(1)
    mock_request.assert_called_once_with(
        method="GET",
        url=f"{RHESIS_BASE_URL}/test/1",
        headers={
            "Authorization": f"Bearer {RHESIS_API_KEY}",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )


# def test_pull(test_entity_without_id):
#     with pytest.raises(ValueError):
#         test_entity_without_id.pull()


# def test_delete(test_entity_without_id):
#     with pytest.raises(ValueError):
#         test_entity_without_id.delete()


# def test_push(test_entity, test_entity_without_id):
#     test_entity.push()
#     test_entity_without_id.push()
