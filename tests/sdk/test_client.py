from unittest.mock import Mock, patch

import pytest
import requests
from rhesis.sdk.client import Client, Endpoints, Methods


@pytest.fixture
def mock_client():
    return Mock(spec=Client)


def test_client_init():
    client = Client(api_key="test_api_key", base_url="https://test.example.com")
    assert client.api_key == "test_api_key"
    assert client.base_url == "https://test.example.com"
    assert client.headers == {
        "Authorization": "Bearer test_api_key",
        "Content-Type": "application/json",
    }


def test_client_uses_env_api_key(monkeypatch):
    """Test that Client uses API key from environment variable."""
    # Set environment variable
    monkeypatch.setenv("RHESIS_API_KEY", "env_test_key")
    monkeypatch.setenv("RHESIS_BASE_URL", "https://test.example.com")

    # Create client without explicit API key
    client = Client()

    # Should use the environment variable
    assert client.api_key == "env_test_key"
    assert client.base_url == "https://test.example.com"
    assert client.headers == {
        "Authorization": "Bearer env_test_key",
        "Content-Type": "application/json",
    }


def test_base_url():
    client = Client(base_url="https://test.example.com/")
    assert client.base_url == "https://test.example.com"


def test_get_url():
    client = Client(base_url="https://test.example.com/")
    assert client.get_url("behaviors") == "https://test.example.com/behaviors"
    assert client.get_url("/behaviors") == "https://test.example.com/behaviors"
    assert client.get_url("behaviors/1") == "https://test.example.com/behaviors/1"
    assert client.get_url("/behaviors/1") == "https://test.example.com/behaviors/1"


@patch("requests.request")
def test_send_request_get(mock_request):
    """Test send_request with GET method."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success", "data": []}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")
    result = client.send_request(Endpoints.BEHAVIORS, Methods.GET)

    # Verify the request was made correctly
    mock_request.assert_called_once_with(
        method="GET",
        url="https://test.example.com/behaviors",
        headers=client.headers,
        json=None,
        params=None,
    )

    # Verify the response
    assert result == {"status": "success", "data": []}


@patch("requests.request")
def test_send_request_post_with_data(mock_request):
    """Test send_request with POST method and data."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"status": "created", "id": 123}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")
    data = {"name": "test_behavior", "type": "custom"}
    result = client.send_request(Endpoints.BEHAVIORS, Methods.POST, data=data)

    # Verify the request was made correctly
    mock_request.assert_called_once_with(
        method="POST",
        url="https://test.example.com/behaviors",
        headers=client.headers,
        json=data,
        params=None,
    )

    # Verify the response
    assert result == {"status": "created", "id": 123}


@patch("requests.request")
def test_send_request_with_params(mock_request):
    """Test send_request with query parameters."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success", "data": []}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")
    params = {"limit": 10, "offset": 0}
    result = client.send_request(Endpoints.METRICS, Methods.GET, params=params)

    # Verify the request was made correctly
    mock_request.assert_called_once_with(
        method="GET",
        url="https://test.example.com/metrics",
        headers=client.headers,
        json=None,
        params=params,
    )

    # Verify the response
    assert result == {"status": "success", "data": []}


@patch("requests.request")
def test_send_request_with_url_params(mock_request):
    """Test send_request with URL parameters."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success", "id": 123}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")
    result = client.send_request(Endpoints.BEHAVIORS, Methods.GET, url_params="123")

    # Verify the request was made correctly
    mock_request.assert_called_once_with(
        method="GET",
        url="https://test.example.com/behaviors/123",
        headers=client.headers,
        json=None,
        params=None,
    )

    # Verify the response
    assert result == {"status": "success", "id": 123}


@patch("requests.request")
def test_send_request_put_with_all_params(mock_request):
    """Test send_request with PUT method and all parameters."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"status": "updated", "id": 123}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")
    data = {"name": "updated_behavior"}
    params = {"version": "1.0"}
    result = client.send_request(
        Endpoints.BEHAVIORS, Methods.PUT, data=data, params=params, url_params="123"
    )

    # Verify the request was made correctly
    mock_request.assert_called_once_with(
        method="PUT",
        url="https://test.example.com/behaviors/123",
        headers=client.headers,
        json=data,
        params=params,
    )

    # Verify the response
    assert result == {"status": "updated", "id": 123}


@patch("requests.request")
def test_send_request_http_error(mock_request):
    """Test send_request raises HTTPError for bad status codes."""
    # Mock response with HTTP error
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")

    with pytest.raises(requests.HTTPError, match="404 Not Found"):
        client.send_request(Endpoints.BEHAVIORS, Methods.GET)


@patch("requests.request")
def test_send_request_all_endpoints(mock_request):
    """Test send_request works with all endpoint types."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success"}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")

    # Test all endpoints
    for endpoint in Endpoints:
        result = client.send_request(endpoint, Methods.GET)
        assert result == {"status": "success"}

    # Should have been called for each endpoint
    assert mock_request.call_count == len(Endpoints)


@patch("requests.request")
def test_send_request_all_methods(mock_request):
    """Test send_request works with all HTTP methods."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success"}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    client = Client(api_key="test_key", base_url="https://test.example.com")

    # Test all methods
    for method in Methods:
        result = client.send_request(Endpoints.BEHAVIORS, method)
        assert result == {"status": "success"}

    # Should have been called for each method
    assert mock_request.call_count == len(Methods)
