import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.test_result import TestResult
from rhesis.sdk.entities.status import Status

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


@pytest.fixture
def test_result_data():
    """Fixture for test result data with nested status."""
    return {
        "id": "result-123",
        "test_configuration_id": "config-456",
        "test_run_id": "run-789",
        "prompt_id": "prompt-012",
        "test_id": "test-345",
        "status_id": "status-678",
        "status": {
            "id": "status-678",
            "name": "Passed",
            "description": "Test passed successfully",
        },
        "test_output": {"response": "Test output"},
        "test_metrics": {"accuracy": 0.95},
        "test_reviews": {"reviewer": "John Doe"},
    }


@pytest.fixture
def test_result_with_status(test_result_data):
    """Fixture for test result entity with nested status."""
    return TestResult(**test_result_data)


def test_test_result_creates_with_nested_status(test_result_with_status):
    """Test TestResult can be created with nested Status object."""
    assert test_result_with_status.id == "result-123"
    assert test_result_with_status.status_id == "status-678"
    assert test_result_with_status.status is not None
    assert isinstance(test_result_with_status.status, Status)
    assert test_result_with_status.status.name == "Passed"
    assert test_result_with_status.status.description == "Test passed successfully"
    assert test_result_with_status.status.id == "status-678"


def test_test_result_without_status():
    """Test TestResult can be created without status object."""
    result = TestResult(
        test_configuration_id="config-123",
        test_run_id="run-456",
        status_id="status-789",
        id="result-012",
    )
    assert result.status_id == "status-789"
    assert result.status is None


@patch("requests.request")
def test_pull_test_result_with_nested_status(mock_request, test_result_data):
    """Test pulling a test result from API with nested status."""
    # Mock the response
    mock_response = MagicMock()
    mock_response.json.return_value = test_result_data
    mock_request.return_value = mock_response

    # Pull the entity
    from rhesis.sdk.entities.test_result import TestResults

    result = TestResults.pull("result-123")

    # Verify the request
    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test_results/result-123",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )

    # Verify the result has nested status
    assert result.id == "result-123"
    assert result.status is not None
    assert isinstance(result.status, Status)
    assert result.status.name == "Passed"


def test_test_result_model_dump_includes_status(test_result_with_status):
    """Test that model_dump includes the nested status object."""
    dumped = test_result_with_status.model_dump()
    assert "status" in dumped
    assert dumped["status"] is not None
    assert dumped["status"]["name"] == "Passed"
    assert dumped["status"]["id"] == "status-678"

