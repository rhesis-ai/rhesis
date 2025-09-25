import os
from enum import Enum
from unittest.mock import patch

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
