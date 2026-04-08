import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TEST_RUN_STATS_ALL = {
    "status_distribution": [
        {"status": "Completed", "count": 34, "percentage": 100.0},
    ],
    "result_distribution": {
        "total": 226,
        "passed": 59,
        "failed": 167,
        "pending": 0,
        "pass_rate": 26.11,
    },
    "most_run_test_sets": [
        {"test_set_name": "Safety Evaluation", "run_count": 9},
        {"test_set_name": "Multi-Turn", "run_count": 2},
    ],
    "top_executors": [
        {"executor_name": "alice@example.com", "run_count": 34},
    ],
    "timeline": [
        {
            "date": "2026-01",
            "total_runs": 10,
            "result_breakdown": {"passed": 8, "failed": 2, "pending": 0},
        },
    ],
    "overall_summary": {
        "total_runs": 34,
        "unique_test_sets": 5,
        "unique_executors": 1,
        "most_common_status": "Completed",
        "pass_rate": 26.11,
    },
    "metadata": {
        "generated_at": "2026-03-22T12:00:00",
        "organization_id": "org-123",
        "period": "Last 6 months",
        "start_date": "2025-09-22T12:00:00",
        "end_date": "2026-03-22T12:00:00",
        "total_test_runs": 34,
        "mode": "all",
        "available_statuses": ["Completed"],
        "available_test_sets": ["Safety Evaluation", "Multi-Turn"],
        "available_executors": ["alice@example.com"],
    },
}

SAMPLE_TEST_RESULT_STATS_TOPIC = {
    "topic_pass_rates": {
        "Safety": {"total": 50, "passed": 40, "failed": 10, "pass_rate": 80.0},
        "Accuracy": {"total": 30, "passed": 25, "failed": 5, "pass_rate": 83.33},
    },
    "metadata": {
        "generated_at": "2026-03-22T12:00:00",
        "organization_id": "org-123",
        "period": "Last 6 months",
        "start_date": "2025-09-22T12:00:00",
        "end_date": "2026-03-22T12:00:00",
        "total_test_runs": 10,
        "total_test_results": 80,
        "mode": "topic",
        "available_metrics": [],
        "available_behaviors": [],
        "available_categories": [],
        "available_topics": ["Safety", "Accuracy"],
    },
}

SAMPLE_TEST_RUN_STATS_STATUS = {
    "status_distribution": [
        {"status": "Completed", "count": 34, "percentage": 100.0},
    ],
    "metadata": {
        "generated_at": "2026-03-22T12:00:00",
        "mode": "status",
        "total_test_runs": 34,
        "period": "Last 6 months",
        "start_date": "2025-09-22",
        "end_date": "2026-03-22",
        "available_statuses": ["Completed"],
        "available_test_sets": [],
        "available_executors": [],
    },
}


# ---------------------------------------------------------------------------
# Mode enums
# ---------------------------------------------------------------------------


class TestRunStatsModeEnum:
    def test_values_are_strings(self):
        from rhesis.sdk.entities.stats import TestRunStatsMode

        assert TestRunStatsMode.ALL == "all"
        assert TestRunStatsMode.STATUS == "status"
        assert TestRunStatsMode.TIMELINE == "timeline"

    def test_is_str_subclass(self):
        from rhesis.sdk.entities.stats import TestRunStatsMode

        assert isinstance(TestRunStatsMode.ALL, str)

    def test_value_access(self):
        from rhesis.sdk.entities.stats import TestRunStatsMode

        assert TestRunStatsMode.ALL.value == "all"
        assert TestRunStatsMode.STATUS.value == "status"


class TestResultStatsModeEnum:
    def test_values_are_strings(self):
        from rhesis.sdk.entities.stats import TestResultStatsMode

        assert TestResultStatsMode.ALL == "all"
        assert TestResultStatsMode.TOPIC == "topic"
        assert TestResultStatsMode.BEHAVIOR == "behavior"
        assert TestResultStatsMode.CATEGORY == "category"
        assert TestResultStatsMode.METRICS == "metrics"

    def test_is_str_subclass(self):
        from rhesis.sdk.entities.stats import TestResultStatsMode

        assert isinstance(TestResultStatsMode.TOPIC, str)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestTestRunStatsModel:
    def test_validates_full_response(self):
        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate(SAMPLE_TEST_RUN_STATS_ALL)
        assert stats.metadata.total_test_runs == 34
        assert stats.result_distribution.pass_rate == 26.11
        assert len(stats.status_distribution) == 1
        assert stats.status_distribution[0].status == "Completed"
        assert len(stats.most_run_test_sets) == 2
        assert len(stats.top_executors) == 1
        assert len(stats.timeline) == 1
        assert stats.overall_summary.most_common_status == "Completed"

    def test_validates_partial_response(self):
        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate(SAMPLE_TEST_RUN_STATS_STATUS)
        assert stats.status_distribution is not None
        assert stats.result_distribution is None
        assert stats.timeline is None
        assert stats.metadata.mode == "status"

    def test_empty_response(self):
        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate({})
        assert stats.status_distribution is None
        assert stats.metadata is None


class TestTestResultStatsModel:
    def test_validates_topic_response(self):
        from rhesis.sdk.entities.stats import TestResultStats

        stats = TestResultStats.model_validate(SAMPLE_TEST_RESULT_STATS_TOPIC)
        assert stats.topic_pass_rates is not None
        assert "Safety" in stats.topic_pass_rates
        assert stats.topic_pass_rates["Safety"].pass_rate == 80.0
        assert stats.metadata.mode == "topic"
        assert stats.behavior_pass_rates is None

    def test_empty_response(self):
        from rhesis.sdk.entities.stats import TestResultStats

        stats = TestResultStats.model_validate({})
        assert stats.topic_pass_rates is None
        assert stats.metadata is None


# ---------------------------------------------------------------------------
# TestRuns.stats()
# ---------------------------------------------------------------------------


@patch("requests.request")
def test_test_runs_stats_calls_correct_endpoint(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RUN_STATS_ALL
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.test_run import TestRuns

    stats = TestRuns.stats(mode="all", months=6, top=5)

    mock_request.assert_called_once()
    call_kwargs = mock_request.call_args
    assert call_kwargs.kwargs["method"] == "GET"
    assert call_kwargs.kwargs["url"] == "http://test:8000/test_runs/stats"
    assert call_kwargs.kwargs["params"]["mode"] == "all"
    assert call_kwargs.kwargs["params"]["months"] == 6
    assert call_kwargs.kwargs["params"]["top"] == 5

    assert stats.metadata.total_test_runs == 34
    assert stats.result_distribution.passed == 59


@patch("requests.request")
def test_test_runs_stats_with_enum_mode(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RUN_STATS_STATUS
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.stats import TestRunStatsMode
    from rhesis.sdk.entities.test_run import TestRuns

    stats = TestRuns.stats(mode=TestRunStatsMode.STATUS)

    call_kwargs = mock_request.call_args
    assert call_kwargs.kwargs["params"]["mode"] == "status"
    assert stats.status_distribution is not None


@patch("requests.request")
def test_test_runs_stats_passes_list_filters(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RUN_STATS_ALL
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.test_run import TestRuns

    TestRuns.stats(
        mode="all",
        test_run_ids=["id1", "id2"],
        test_set_ids=["ts1"],
    )

    call_kwargs = mock_request.call_args
    assert call_kwargs.kwargs["params"]["test_run_ids"] == ["id1", "id2"]
    assert call_kwargs.kwargs["params"]["test_set_ids"] == ["ts1"]


@patch("requests.request")
def test_test_runs_stats_omits_none_params(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RUN_STATS_ALL
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.test_run import TestRuns

    TestRuns.stats(mode="all")

    call_kwargs = mock_request.call_args
    params = call_kwargs.kwargs["params"]
    assert "months" not in params
    assert "top" not in params
    assert "test_run_ids" not in params


# ---------------------------------------------------------------------------
# TestRun.stats() (instance method)
# ---------------------------------------------------------------------------


@patch("requests.request")
def test_test_run_instance_stats_delegates(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RUN_STATS_ALL
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.test_run import TestRun

    run = TestRun(id="run-abc")
    stats = run.stats(months=3)

    call_kwargs = mock_request.call_args
    assert call_kwargs.kwargs["params"]["test_run_ids"] == ["run-abc"]
    assert call_kwargs.kwargs["params"]["months"] == 3
    assert stats.metadata is not None


def test_test_run_instance_stats_raises_without_id():
    from rhesis.sdk.entities.test_run import TestRun

    run = TestRun(name="No ID Run")
    with pytest.raises(ValueError, match="Test run ID is required"):
        run.stats()


# ---------------------------------------------------------------------------
# TestResults.stats()
# ---------------------------------------------------------------------------


@patch("requests.request")
def test_test_results_stats_calls_correct_endpoint(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RESULT_STATS_TOPIC
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.test_result import TestResults

    stats = TestResults.stats(mode="topic", months=6)

    mock_request.assert_called_once()
    call_kwargs = mock_request.call_args
    assert call_kwargs.kwargs["method"] == "GET"
    assert call_kwargs.kwargs["url"] == "http://test:8000/test_results/stats"
    assert call_kwargs.kwargs["params"]["mode"] == "topic"

    assert stats.topic_pass_rates is not None
    assert "Safety" in stats.topic_pass_rates


@patch("requests.request")
def test_test_results_stats_with_enum_mode(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RESULT_STATS_TOPIC
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.stats import TestResultStatsMode
    from rhesis.sdk.entities.test_result import TestResults

    TestResults.stats(mode=TestResultStatsMode.TOPIC)

    call_kwargs = mock_request.call_args
    assert call_kwargs.kwargs["params"]["mode"] == "topic"


@patch("requests.request")
def test_test_results_stats_passes_filters(mock_request):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_TEST_RESULT_STATS_TOPIC
    mock_request.return_value = mock_response

    from rhesis.sdk.entities.test_result import TestResults

    TestResults.stats(
        mode="topic",
        topic_ids=["t1", "t2"],
        behavior_ids=["b1"],
        tags=["safety"],
        priority_min=1,
    )

    call_kwargs = mock_request.call_args
    params = call_kwargs.kwargs["params"]
    assert params["topic_ids"] == ["t1", "t2"]
    assert params["behavior_ids"] == ["b1"]
    assert params["tags"] == ["safety"]
    assert params["priority_min"] == 1


# ---------------------------------------------------------------------------
# to_dataframe()
# ---------------------------------------------------------------------------


class TestToDataframe:
    def test_list_section_to_dataframe(self):
        pytest.importorskip("pandas")
        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate(SAMPLE_TEST_RUN_STATS_ALL)
        df = stats.to_dataframe("status_distribution")
        assert len(df) == 1
        assert "status" in df.columns
        assert df.iloc[0]["status"] == "Completed"

    def test_dict_section_to_dataframe(self):
        pytest.importorskip("pandas")
        from rhesis.sdk.entities.stats import TestResultStats

        stats = TestResultStats.model_validate(SAMPLE_TEST_RESULT_STATS_TOPIC)
        df = stats.to_dataframe("topic_pass_rates")
        assert len(df) == 2
        assert "Safety" in df.index
        assert "pass_rate" in df.columns

    def test_timeline_to_dataframe(self):
        pytest.importorskip("pandas")
        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate(SAMPLE_TEST_RUN_STATS_ALL)
        df = stats.to_dataframe("timeline")
        assert len(df) == 1
        assert "date" in df.columns

    def test_none_section_returns_empty_dataframe(self):
        pytest.importorskip("pandas")
        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate({})
        df = stats.to_dataframe("timeline")
        assert len(df) == 0

    def test_raises_import_error_without_pandas(self):
        import builtins
        from unittest.mock import patch as _patch

        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate(SAMPLE_TEST_RUN_STATS_ALL)

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pandas":
                raise ImportError("No module named 'pandas'")
            return real_import(name, *args, **kwargs)

        with _patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="pandas is required"):
                stats.to_dataframe("timeline")

    def test_invalid_section_raises_attribute_error(self):
        from rhesis.sdk.entities.stats import TestRunStats

        stats = TestRunStats.model_validate(SAMPLE_TEST_RUN_STATS_ALL)
        with pytest.raises(AttributeError):
            stats.to_dataframe("nonexistent_field")
