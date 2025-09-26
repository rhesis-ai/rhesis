import os
from enum import Enum
from unittest.mock import MagicMock, patch

from requests.exceptions import HTTPError
from rhesis.sdk.client import HTTPStatus
from rhesis.sdk.entities.base_collection import BaseCollection

os.environ["RHESIS_API_KEY"] = "test_api_key"
os.environ["RHESIS_BASE_URL"] = "http://test:8000"


class TestEndpoint(Enum):
    TEST = "test"


class TestBaseCollection(BaseCollection):
    endpoint = TestEndpoint.TEST


@patch("requests.request")
def test_all(mock_request):
    TestBaseCollection.all()

    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test",
        headers={
            "Authorization": "Bearer test_api_key",
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
            "Authorization": "Bearer test_api_key",
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
