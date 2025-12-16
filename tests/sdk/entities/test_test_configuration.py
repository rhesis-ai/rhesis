import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.test_configuration import TestConfiguration

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


@pytest.fixture
def test_configuration():
    """Fixture for test configuration entity."""
    return TestConfiguration(
        endpoint_id="endpoint-123",
        category_id="category-456",
        topic_id="topic-789",
        prompt_id="prompt-012",
        test_set_id="testset-345",
        user_id="user-678",
        organization_id="org-901",
        status_id="status-234",
        id="config-567",
    )


@pytest.fixture
def test_configuration_without_id():
    """Fixture for test configuration entity without ID."""
    return TestConfiguration(
        endpoint_id="endpoint-123",
        category_id="category-456",
        id=None,
    )


@patch("requests.request")
def test_get_test_runs(mock_request, test_configuration):
    """Test get_test_runs method filters by test_configuration_id."""
    # Mock the response
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "id": "run-1",
            "test_configuration_id": "config-567",
            "name": "Test Run 1",
            "status_id": "status-1",
        },
        {
            "id": "run-2",
            "test_configuration_id": "config-567",
            "name": "Test Run 2",
            "status_id": "status-2",
        },
    ]
    mock_request.return_value = mock_response

    # Call the method
    result = test_configuration.get_test_runs()

    # Verify the request was made correctly
    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test_runs",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params={"$filter": "test_configuration_id eq 'config-567'"},
    )

    # Verify the result
    assert result is not None


def test_get_test_runs_without_id(test_configuration_without_id):
    """Test get_test_runs raises ValueError when ID is None."""
    with pytest.raises(ValueError, match="Test configuration ID is required"):
        test_configuration_without_id.get_test_runs()

