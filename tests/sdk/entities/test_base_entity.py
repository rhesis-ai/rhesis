import logging
import os
from enum import Enum
from typing import ClassVar, Optional
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from rhesis.sdk.clients import HTTPStatus
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors
from rhesis.sdk.errors import RhesisAPIError

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


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
        url="http://test:8000/test/1",
        headers={
            "Authorization": "Bearer rh-test-token",
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
        url="http://test:8000/test/1",
        headers={
            "Authorization": "Bearer rh-test-token",
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
        url="http://test:8000/test",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json={"name": "Test", "description": "Test"},
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
        url="http://test:8000/test/1",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )


class TestHandleHttpErrorsSecurity:
    """Verify that handle_http_errors never leaks credentials."""

    API_KEY = "rh-SUPER_SECRET_KEY_12345"

    def _make_http_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"Internal Server Error"
        mock_response.request = MagicMock()
        mock_response.request.url = "http://test:8000/test/1"
        mock_response.request.method = "POST"
        mock_response.request.headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }
        mock_response.request.body = b'{"auth_token": "secret-token-value"}'
        error = HTTPError("500 Server Error", response=mock_response)
        return error

    def test_no_api_key_in_logs(self, caplog):
        """Authorization header must never appear in log output."""

        @handle_http_errors
        def failing_method(self_arg):
            raise self._make_http_error()

        with caplog.at_level(logging.ERROR, logger="rhesis.sdk.entities.base_entity"):
            with pytest.raises(RhesisAPIError):
                failing_method(None)

        full_log = caplog.text
        assert self.API_KEY not in full_log, "API key was leaked in log output"
        assert "Bearer" not in full_log, "Authorization header was leaked in log output"
        assert "auth_token" not in full_log, "Request body was leaked in log output"

    def test_raises_rhesis_api_error(self):
        """handle_http_errors must raise RhesisAPIError, not return None."""

        @handle_http_errors
        def failing_method(self_arg):
            raise self._make_http_error()

        with pytest.raises(RhesisAPIError) as exc_info:
            failing_method(None)

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_content == "Internal Server Error"

    def test_preserves_original_exception(self):
        """RhesisAPIError must chain from the original HTTPError."""

        @handle_http_errors
        def failing_method(self_arg):
            raise self._make_http_error()

        with pytest.raises(RhesisAPIError) as exc_info:
            failing_method(None)

        assert isinstance(exc_info.value.__cause__, HTTPError)
