import os
from enum import Enum
from unittest.mock import MagicMock, patch

from requests.exceptions import HTTPError
from rhesis.sdk.client import HTTPStatus
from rhesis.sdk.entities.base_entity import BaseEntity

os.environ["RHESIS_API_KEY"] = "test_api_key"
os.environ["RHESIS_BASE_URL"] = "http://test:8000"


class TestEndpoint(Enum):
    TEST = "test"


class TestEntity(BaseEntity):
    endpoint = TestEndpoint.TEST


@patch("requests.request")
def test_delete_by_id(mock_request):
    record_id = 1
    entity = TestEntity()
    entity.delete_by_id(record_id)
    mock_request.assert_called_once_with(
        method="DELETE",
        url="http://test:8000/test/1",
        headers={
            "Authorization": "Bearer test_api_key",
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
    entity = TestEntity()
    result = entity.delete_by_id(record_id)
    assert result is False


@patch("requests.request")
def test_save_with_id(mock_request):
    entity = TestEntity()
    entity.fields = {"id": 1, "name": "Test", "description": "Test"}
    entity.save()
    mock_request.assert_called_once_with(
        method="PUT",
        url="http://test:8000/test/1",
        headers={
            "Authorization": "Bearer test_api_key",
            "Content-Type": "application/json",
        },
        json={"name": "Test", "description": "Test"},
        params=None,
    )


@patch("requests.request")
def test_save_without_id(mock_request):
    entity = TestEntity()
    entity.fields = {"name": "Test", "description": "Test"}
    entity.save()
    mock_request.assert_called_once_with(
        method="POST",
        url="http://test:8000/test",
        headers={
            "Authorization": "Bearer test_api_key",
            "Content-Type": "application/json",
        },
        json={"name": "Test", "description": "Test"},
        params=None,
    )


@patch("requests.request")
def test_fetch(mock_request):
    mock_request.return_value.json.return_value = {
        "id": 2,
        "name": "Test2",
        "description": "Test2",
    }
    entity = TestEntity()
    entity.fields = {"id": 1, "name": "Test", "description": "Test"}
    entity.fetch()
    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test/1",
        headers={
            "Authorization": "Bearer test_api_key",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )
    assert entity.fields == {"id": 2, "name": "Test2", "description": "Test2"}


@patch("requests.request")
def test_from_id(mock_request):
    mock_request.return_value.json.return_value = {
        "id": 1,
        "name": "Test",
        "description": "Test",
    }
    entity = TestEntity.from_id(1)
    assert entity.fields == {"id": 1, "name": "Test", "description": "Test"}
    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test/1",
        headers={
            "Authorization": "Bearer test_api_key",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )
