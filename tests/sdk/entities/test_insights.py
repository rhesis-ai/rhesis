import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.config import DEFAULT_API_TIMEOUT
from rhesis.sdk.entities import Insights
from rhesis.sdk.entities.test_result import TestResults
from rhesis.sdk.entities.test_run import TestRun, TestRuns

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


@pytest.fixture
def insights_response():
    """Fixture for a GET /insights aggregation response."""
    return {
        "entity": "test_result",
        "dimensions": ["requirement"],
        "measures": ["count", "pass_rate"],
        "rows": [{"requirement": "refund", "count": 10, "pass_rate": 80.0}],
    }


@pytest.fixture
def insights_ids_response():
    """Fixture for a GET /insights/ids response."""
    return {"entity": "test_result", "ids": ["test-1", "test-2"]}


@patch("requests.request")
def test_insights_get_sends_entity_group_by_measures_and_filters(mock_request, insights_response):
    """Test that get() forwards entity, group_by, measures, and filters as query params."""
    mock_response = MagicMock()
    mock_response.json.return_value = insights_response
    mock_request.return_value = mock_response

    result = Insights(
        entity="test_result",
        group_by=["requirement"],
        measures=["count", "pass_rate"],
        filters={"test_run_ids": ["run-1"]},
    ).get()

    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/insights",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params={
            "entity": "test_result",
            "test_run_ids": ["run-1"],
            "group_by": ["requirement"],
            "measures": ["count", "pass_rate"],
        },
        timeout=DEFAULT_API_TIMEOUT,
    )
    assert result.rows[0]["requirement"] == "refund"


@patch("requests.request")
def test_insights_get_omits_unset_group_by_and_filters(mock_request, insights_response):
    """Test that empty group_by/filters are left out of the query params entirely."""
    mock_response = MagicMock()
    mock_response.json.return_value = insights_response
    mock_request.return_value = mock_response

    Insights(entity="test_result", measures=["count"]).get()

    _, kwargs = mock_request.call_args
    assert kwargs["params"] == {"entity": "test_result", "measures": ["count"]}


@patch("requests.request")
def test_insights_ids_hits_ids_endpoint_with_outcome(mock_request, insights_ids_response):
    """Test that ids() reuses the same filters and hits /insights/ids with the outcome param."""
    mock_response = MagicMock()
    mock_response.json.return_value = insights_ids_response
    mock_request.return_value = mock_response

    result = Insights(entity="test_result", filters={"test_run_ids": ["run-1"]}).ids(outcome="fail")

    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/insights/ids",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params={"entity": "test_result", "test_run_ids": ["run-1"], "outcome": "fail"},
        timeout=DEFAULT_API_TIMEOUT,
    )
    assert result.ids == ["test-1", "test-2"]


def test_test_results_stats_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Insights"):
        TestResults.stats()


def test_test_runs_stats_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Insights"):
        TestRuns.stats()


def test_test_run_instance_stats_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Insights"):
        TestRun(id="run-1").stats()
