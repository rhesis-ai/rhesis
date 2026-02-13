"""Integration tests for TestSet execution methods.

These tests require a running backend (via docker-compose).
The execute endpoint needs Celery workers that are not present in
the test environment, so the actual HTTP call for ``execute()`` is
mocked at the SDK level while all other calls (test set / endpoint /
metric creation) hit the real backend.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests as _requests

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.test_set import TestSet

# Keep reference to the real ``requests.request`` so that setup
# calls (test-set / endpoint / metric creation) still hit the
# live backend.
_real_request = _requests.request

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _create_endpoint(name: str = "Execute Test Endpoint") -> Endpoint:
    """Create a minimal REST endpoint for execution tests."""
    ep = Endpoint(
        name=name,
        description="Integration test endpoint",
        connection_type="REST",
        url="https://httpbin.org/post",
        project_id="12340000-0000-4000-8000-000000001234",
        method="POST",
        endpoint_path="/v1/chat",
        request_mapping={"message": "{{ input }}"},
        response_mapping={"output": "result.text"},
    )
    result = ep.push()
    assert result is not None and "id" in result, "Endpoint creation failed"
    return ep


def _create_metric(name: str) -> dict:
    """Create a metric via the backend API and return its dict."""
    client = APIClient()
    return client.send_request(
        endpoint=Endpoints.METRICS,
        method=Methods.POST,
        data={
            "name": name,
            "description": f"Integration test metric: {name}",
            "evaluation_prompt": "Rate the response.",
            "score_type": "numeric",
            "min_score": 0,
            "max_score": 1,
            "threshold": 0.5,
        },
    )


def _create_test_set(
    name: str = "Execution Test Set",
) -> TestSet:
    """Create a minimal test set via the bulk endpoint."""
    ts = TestSet(
        name=name,
        description="Integration test set for execution",
        short_description="Test",
        tests=[
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Compliance",
                "prompt": {"content": "Hello, is this safe?"},
            }
        ],
    )
    ts.push()
    assert ts.id is not None, "Test set creation failed"
    return ts


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def _mock_execute_response():
    """Return a MagicMock that behaves like a successful execute response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "submitted",
        "task_id": "mock-task-id",
    }
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _selective_mock(execute_url_fragment, mock_resp):
    """Return a side_effect that mocks only URLs containing *execute_url_fragment*."""

    def _side_effect(*args, **kwargs):
        url = kwargs.get("url", args[1] if len(args) > 1 else "")
        if execute_url_fragment in url:
            return mock_resp
        return _real_request(*args, **kwargs)

    return _side_effect


class TestExecute:
    """Execute tests.

    The execute endpoint requires Celery workers which are not
    available in the docker-compose test environment.  We mock the
    HTTP call for the ``/execute/`` request only, while all other
    API calls (test set creation, endpoint creation, metric creation)
    hit the real backend.
    """

    @patch("requests.request")
    def test_execute_default(self, mock_request, db_cleanup):
        """Default execute sends correct body and returns submission."""
        mock_resp = _mock_execute_response()
        mock_request.side_effect = _selective_mock("/execute/", mock_resp)

        ts = _create_test_set()
        ep = _create_endpoint()

        result = ts.execute(ep)

        assert result is not None
        assert result["status"] == "submitted"

        # Find the execute call among all calls
        execute_calls = [c for c in mock_request.call_args_list if "/execute/" in str(c)]
        assert len(execute_calls) == 1
        body = execute_calls[0][1]["json"]
        assert body["execution_options"]["execution_mode"] == "Parallel"

    @patch("requests.request")
    def test_execute_sequential(self, mock_request, db_cleanup):
        """Sequential mode is sent in the body."""
        mock_resp = _mock_execute_response()
        mock_request.side_effect = _selective_mock("/execute/", mock_resp)

        ts = _create_test_set()
        ep = _create_endpoint("Sequential Endpoint")

        result = ts.execute(ep, mode="sequential")

        assert result is not None
        assert result["status"] == "submitted"

        execute_calls = [c for c in mock_request.call_args_list if "/execute/" in str(c)]
        assert len(execute_calls) == 1
        body = execute_calls[0][1]["json"]
        assert body["execution_options"]["execution_mode"] == "Sequential"

    @patch("requests.request")
    def test_execute_with_metrics(self, mock_request, db_cleanup):
        """Metrics are included in the execute body."""
        mock_resp = _mock_execute_response()
        mock_request.side_effect = _selective_mock("/execute/", mock_resp)

        ts = _create_test_set()
        ep = _create_endpoint("Metrics Endpoint")
        metric = _create_metric("ExecMetric")

        result = ts.execute(
            ep,
            metrics=[{"id": str(metric["id"]), "name": "ExecMetric"}],
        )

        assert result is not None
        assert result["status"] == "submitted"

        execute_calls = [c for c in mock_request.call_args_list if "/execute/" in str(c)]
        assert len(execute_calls) == 1
        body = execute_calls[0][1]["json"]
        assert "metrics" in body
        assert len(body["metrics"]) == 1
        assert body["metrics"][0]["name"] == "ExecMetric"


class TestRescore:
    def test_rescore_no_completed_run_raises(self, db_cleanup):
        """Rescore without a prior run raises ValueError."""
        ts = _create_test_set()
        ep = _create_endpoint("Rescore Endpoint")

        with pytest.raises(ValueError, match="No completed test run found"):
            ts.rescore(ep)


class TestLastRun:
    def test_last_run_no_runs(self, db_cleanup):
        """last_run returns None when no runs exist."""
        ts = _create_test_set()
        ep = _create_endpoint("LastRun Endpoint")

        result = ts.last_run(ep)

        # handle_http_errors returns None on 404
        assert result is None
