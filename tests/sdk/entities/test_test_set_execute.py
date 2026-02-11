import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.enums import ExecutionMode
from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.test_set import TestSet

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


# --- Fixtures ---


@pytest.fixture
def test_set():
    """A test set with an ID."""
    return TestSet(
        id="ts-111",
        name="Safety Tests",
        description="Safety test set",
        short_description="Safety",
    )


@pytest.fixture
def test_set_no_id():
    """A test set without an ID."""
    return TestSet(
        name="Safety Tests",
        description="Safety test set",
        short_description="Safety",
    )


@pytest.fixture
def endpoint():
    """An endpoint entity."""
    return Endpoint(
        id="ep-222",
        name="GPT-4o",
        description="GPT-4o endpoint",
        short_description="GPT-4o",
        url="https://api.openai.com/v1/chat/completions",
    )


# ================================================================
# Tests for execute()
# ================================================================


class TestExecute:
    """Tests for TestSet.execute()."""

    @patch("requests.request")
    def test_execute_default(self, mock_request, test_set, endpoint):
        """Default execute sends mode=Parallel, no metrics, no ref run."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "submitted",
            "task_id": "task-aaa",
        }
        mock_request.return_value = mock_response

        result = test_set.execute(endpoint)

        assert result["status"] == "submitted"
        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "POST"
        assert kwargs["url"] == "http://test:8000/test_sets/ts-111/execute/ep-222"
        body = kwargs["json"]
        assert body["execution_options"]["execution_mode"] == "Parallel"
        assert "metrics" not in body
        assert "reference_test_run_id" not in body

    @patch("requests.request")
    def test_execute_sequential_mode(self, mock_request, test_set, endpoint):
        """Sequential mode is capitalized in the body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "submitted"}
        mock_request.return_value = mock_response

        test_set.execute(endpoint, mode="sequential")

        _, kwargs = mock_request.call_args
        body = kwargs["json"]
        assert body["execution_options"]["execution_mode"] == "Sequential"

    @patch("requests.request")
    def test_execute_with_enum_mode(self, mock_request, test_set, endpoint):
        """ExecutionMode enum is accepted and sent correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "submitted"}
        mock_request.return_value = mock_response

        test_set.execute(endpoint, mode=ExecutionMode.SEQUENTIAL)

        _, kwargs = mock_request.call_args
        body = kwargs["json"]
        assert body["execution_options"]["execution_mode"] == "Sequential"

    def test_execute_invalid_mode_raises(self, test_set, endpoint):
        """Invalid execution mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid execution mode"):
            test_set.execute(endpoint, mode="invalid")

    @patch("requests.request")
    def test_execute_with_metric_dicts(self, mock_request, test_set, endpoint):
        """Metric dicts are passed through as-is."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "submitted"}
        mock_request.return_value = mock_response

        metrics = [
            {"id": "m-1", "name": "Accuracy"},
            {"id": "m-2", "name": "Toxicity", "scope": "global"},
        ]
        test_set.execute(endpoint, metrics=metrics)

        _, kwargs = mock_request.call_args
        body = kwargs["json"]
        assert body["metrics"] == metrics

    @patch("requests.request")
    def test_execute_with_metric_names(self, mock_request, test_set, endpoint):
        """Metric name strings trigger a lookup and are resolved to dicts."""
        lookup_response = MagicMock()
        lookup_response.json.return_value = [{"id": "m-resolved", "name": "Toxicity"}]

        execute_response = MagicMock()
        execute_response.json.return_value = {"status": "submitted"}

        mock_request.side_effect = [lookup_response, execute_response]

        test_set.execute(endpoint, metrics=["Toxicity"])

        # First call: metric lookup
        first_call = mock_request.call_args_list[0]
        assert first_call[1]["method"] == "GET"
        assert "metrics" in first_call[1]["url"]
        assert first_call[1]["params"] == {"$filter": "name eq 'Toxicity'"}

        # Second call: execute
        second_call = mock_request.call_args_list[1]
        body = second_call[1]["json"]
        assert len(body["metrics"]) == 1
        assert body["metrics"][0]["id"] == "m-resolved"
        assert body["metrics"][0]["name"] == "Toxicity"

    def test_execute_no_id_raises(self, test_set_no_id, endpoint):
        """ValueError when test set has no ID."""
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.execute(endpoint)


# ================================================================
# Tests for rescore()
# ================================================================


class TestRescore:
    """Tests for TestSet.rescore()."""

    @patch("requests.request")
    def test_rescore_default_latest_run(self, mock_request, test_set, endpoint):
        """run=None fetches last_run and uses its ID."""
        last_run_response = MagicMock()
        last_run_response.json.return_value = {
            "id": "run-latest",
            "name": "Safety - Run 5",
            "status": "Completed",
            "pass_rate": 0.85,
        }

        execute_response = MagicMock()
        execute_response.json.return_value = {"status": "submitted"}

        mock_request.side_effect = [last_run_response, execute_response]

        result = test_set.rescore(endpoint)

        assert result["status"] == "submitted"

        # First call: last-run lookup
        first_call = mock_request.call_args_list[0]
        assert "last-run" in first_call[1]["url"]

        # Second call: execute with reference_test_run_id
        second_call = mock_request.call_args_list[1]
        body = second_call[1]["json"]
        assert body["reference_test_run_id"] == "run-latest"

    @patch("requests.request")
    def test_rescore_no_completed_run_raises(self, mock_request, test_set, endpoint):
        """ValueError when run=None and no completed run exists."""
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

        # last_run returns None due to HTTP error, then rescore raises
        with pytest.raises(ValueError, match="No completed test run found"):
            test_set.rescore(endpoint)

    @patch("requests.request")
    def test_rescore_with_test_run_object(self, mock_request, test_set, endpoint):
        """Passing a TestRun object extracts its ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "submitted"}
        mock_request.return_value = mock_response

        # Create a mock TestRun-like object
        class FakeTestRun:
            id = "run-object-id"

        test_set.rescore(endpoint, run=FakeTestRun())

        _, kwargs = mock_request.call_args
        body = kwargs["json"]
        assert body["reference_test_run_id"] == "run-object-id"

    @patch("requests.request")
    def test_rescore_with_string_id(self, mock_request, test_set, endpoint):
        """Passing a UUID string uses it directly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "submitted"}
        mock_request.return_value = mock_response

        run_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        test_set.rescore(endpoint, run=run_uuid)

        _, kwargs = mock_request.call_args
        body = kwargs["json"]
        assert body["reference_test_run_id"] == run_uuid

    @patch("requests.request")
    def test_rescore_with_run_name(self, mock_request, test_set, endpoint):
        """Passing a name string resolves via TestRuns.pull()."""
        # First call: TestRuns.pull (GET /test_runs?name=...)
        pull_response = MagicMock()
        pull_response.json.return_value = {
            "id": "run-by-name",
            "name": "Safety - Run 42",
        }

        # Second call: execute
        execute_response = MagicMock()
        execute_response.json.return_value = {"status": "submitted"}

        mock_request.side_effect = [pull_response, execute_response]

        test_set.rescore(endpoint, run="Safety - Run 42")

        # Second call should contain the resolved run ID
        second_call = mock_request.call_args_list[1]
        body = second_call[1]["json"]
        assert body["reference_test_run_id"] == "run-by-name"

    @patch("requests.request")
    def test_rescore_with_metrics(self, mock_request, test_set, endpoint):
        """Rescore with custom metrics."""
        # last-run
        last_run_resp = MagicMock()
        last_run_resp.json.return_value = {"id": "run-latest"}

        # metric lookup
        metric_resp = MagicMock()
        metric_resp.json.return_value = [{"id": "m-acc", "name": "Accuracy"}]

        # execute
        exec_resp = MagicMock()
        exec_resp.json.return_value = {"status": "submitted"}

        mock_request.side_effect = [last_run_resp, metric_resp, exec_resp]

        test_set.rescore(endpoint, metrics=["Accuracy"])

        # Third call is the execute
        third_call = mock_request.call_args_list[2]
        body = third_call[1]["json"]
        assert body["reference_test_run_id"] == "run-latest"
        assert len(body["metrics"]) == 1
        assert body["metrics"][0]["id"] == "m-acc"

    def test_rescore_no_id_raises(self, test_set_no_id, endpoint):
        """ValueError when test set has no ID."""
        with pytest.raises(ValueError, match="Test set ID must be set"):
            test_set_no_id.rescore(endpoint)
