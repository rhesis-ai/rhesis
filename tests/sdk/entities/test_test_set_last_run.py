import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.test_set import TestSet

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


# --- Fixtures ---


@pytest.fixture
def test_set():
    return TestSet(
        id="ts-111",
        name="Safety Tests",
        description="Safety test set",
        short_description="Safety",
    )


@pytest.fixture
def test_set_no_id():
    return TestSet(
        name="Safety Tests",
        description="Safety test set",
        short_description="Safety",
    )


@pytest.fixture
def endpoint():
    return Endpoint(
        id="ep-222",
        name="GPT-4o",
        description="GPT-4o endpoint",
        short_description="GPT-4o",
        url="https://api.openai.com/v1/chat/completions",
    )


# ================================================================
# Tests for last_run()
# ================================================================


class TestLastRun:
    """Tests for TestSet.last_run()."""

    @patch("requests.request")
    def test_last_run_success(self, mock_request, test_set, endpoint):
        """Returns summary dict when a completed run exists."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "run-latest",
            "nano_id": "ABC123",
            "name": "Safety - Run 5",
            "status": "Completed",
            "pass_rate": 0.92,
            "test_count": 50,
            "created_at": "2026-01-15T10:00:00Z",
        }
        mock_request.return_value = mock_response

        result = test_set.last_run(endpoint)

        assert result is not None
        assert result["id"] == "run-latest"
        assert result["pass_rate"] == 0.92

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "GET"
        assert kwargs["url"] == "http://test:8000/test_sets/ts-111/last-run/ep-222"

    @patch("requests.request")
    def test_last_run_no_runs(self, mock_request, test_set, endpoint):
        """Returns None when no completed run exists (404)."""
        import requests as req

        mock_response = MagicMock()
        http_error = req.exceptions.HTTPError(response=mock_response)
        mock_response.status_code = 404
        mock_response.content = b"Not found"
        mock_response.request = MagicMock()
        mock_response.request.url = "http://test:8000/test_sets/ts-111/last-run/ep-222"
        mock_response.request.method = "GET"
        mock_response.request.headers = {}
        mock_response.request.body = None
        mock_response.raise_for_status.side_effect = http_error
        mock_request.return_value = mock_response

        result = test_set.last_run(endpoint)

        # handle_http_errors returns None on HTTPError
        assert result is None

    def test_last_run_no_id_raises(self, test_set_no_id, endpoint):
        """ValueError when test set has no ID."""
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.last_run(endpoint)
