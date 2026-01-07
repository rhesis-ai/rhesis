import os
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from rhesis.sdk.client import HTTPStatus
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


class TestEndpoint(Enum):
    __test__ = False
    TEST = "test"


class MockEntity(BaseEntity):
    """Mock entity for testing pull method."""

    id: str
    name: str


class TestBaseCollection(BaseCollection):
    endpoint = TestEndpoint.TEST
    entity_class = MockEntity


@patch("requests.request")
def test_all(mock_request):
    TestBaseCollection.all()

    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )


@patch("requests.request")
def test_exists(mock_request):
    TestBaseCollection.exists(10)

    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test/10",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )

    """Test exists method returns False for nonexistent entity."""
    # Mock unprocessable entity error response
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.NOT_FOUND

    http_error = HTTPError("404 Not Found")
    http_error.response = mock_response
    mock_request.side_effect = http_error

    result = TestBaseCollection.exists(10)

    assert result is False


def test_pull_raises_error_when_no_id_or_name():
    """Test pull method raises ValueError when neither id nor name is provided."""
    with pytest.raises(ValueError, match="Either id or name must be provided"):
        TestBaseCollection.pull()


@patch("requests.request")
def test_pull_with_name(mock_request):
    """Test pull method makes correct request when name is provided."""
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "123", "name": "test-entity"}]
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    TestBaseCollection.pull(name="test-entity")

    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params={"$filter": "tolower(name) eq 'test-entity'"},
    )
