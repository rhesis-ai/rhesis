import os
from unittest.mock import patch

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
# Insights-backed stats() -- TestResults.stats()/TestRuns.stats() no longer
# call a dedicated backend endpoint, they build Insights() queries and reshape
# the rows. These tests patch the Insights class used inside
# rhesis.sdk.entities.stats and check (a) the query it builds and (b) the
# reshaping of a canned response, rather than mocking raw HTTP.
# ---------------------------------------------------------------------------


def _get_response(rows, entity="test_run", dimensions=None, measures=None):
    from rhesis.sdk.entities.insights import InsightsResponse

    return InsightsResponse(
        entity=entity, dimensions=dimensions or [], measures=measures or [], rows=rows
    )


def _test_run_responses(status=None, test_sets=None, executors=None, timeline=None):
    """Canned .get() results, in the order build_test_run_stats queries them."""
    return [
        _get_response(rows=status or []),
        _get_response(rows=test_sets or []),
        _get_response(rows=executors or []),
        _get_response(rows=timeline or []),
    ]


def _test_result_responses(overall=None, behavior=None, category=None, topic=None, metric=None):
    """Canned .get() results, in the order build_test_result_stats queries them.

    ids() is a separate mocked method (.ids), not part of this .get() side_effect list.
    """
    return [
        _get_response(rows=[overall] if overall else [], entity="test_result"),
        _get_response(rows=behavior or [], entity="test_result"),
        _get_response(rows=category or [], entity="test_result"),
        _get_response(rows=topic or [], entity="test_result"),
        _get_response(rows=metric or [], entity="metric"),
    ]


def _ids_response(ids=None):
    from rhesis.sdk.entities.insights import InsightsIdsResponse

    return InsightsIdsResponse(entity="test_result", ids=ids or [])


def _mock_test_result_insights(mock_insights_cls, ids=None, **kwargs):
    """Configure both .get() (section queries) and .ids() (the ids query) on the
    shared Insights mock -- every build_test_result_stats() call needs both."""
    mock_insights_cls.return_value.get.side_effect = _test_result_responses(**kwargs)
    mock_insights_cls.return_value.ids.return_value = _ids_response(ids)


# ---------------------------------------------------------------------------
# TestRuns.stats()
# ---------------------------------------------------------------------------


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_runs_stats_queries_four_sections_regardless_of_mode(mock_insights_cls):
    """mode is no longer a section filter -- it only ends up in metadata.mode."""
    mock_insights_cls.return_value.get.side_effect = _test_run_responses(
        status=[{"status": "Completed", "count": 34}],
    )

    from rhesis.sdk.entities.test_run import TestRuns

    stats = TestRuns.stats(mode="status", months=6)

    assert mock_insights_cls.call_count == 4
    group_bys = [kwargs["group_by"] for _, kwargs in mock_insights_cls.call_args_list]
    assert group_bys == [["status"], ["test_set"], ["executor"], ["year", "month"]]
    first_kwargs = mock_insights_cls.call_args_list[0].kwargs
    assert first_kwargs["filters"] == {}
    assert first_kwargs["months"] == 6
    assert stats.status_distribution[0].status == "Completed"
    assert stats.status_distribution[0].count == 34
    assert stats.status_distribution[0].percentage == 100.0
    assert stats.metadata.mode == "status"


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_runs_stats_with_enum_mode(mock_insights_cls):
    mock_insights_cls.return_value.get.side_effect = _test_run_responses()

    from rhesis.sdk.entities.stats import TestRunStatsMode
    from rhesis.sdk.entities.test_run import TestRuns

    stats = TestRuns.stats(mode=TestRunStatsMode.ALL)

    assert mock_insights_cls.call_count == 4
    assert stats.metadata.mode == "all"


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_runs_stats_passes_filters(mock_insights_cls):
    mock_insights_cls.return_value.get.side_effect = _test_run_responses()

    from rhesis.sdk.entities.test_run import TestRuns

    TestRuns.stats(
        test_run_ids=["id1", "id2"],
        test_set_ids=["ts1"],
        status_list=["Completed"],
    )

    for _, kwargs in mock_insights_cls.call_args_list:
        assert kwargs["filters"] == {
            "test_run_ids": ["id1", "id2"],
            "test_set_ids": ["ts1"],
            "status_names": ["Completed"],
        }


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_runs_stats_applies_top_to_ranked_sections(mock_insights_cls):
    mock_insights_cls.return_value.get.side_effect = _test_run_responses(
        test_sets=[
            {"test_set": "Safety Evaluation", "count": 9},
            {"test_set": "Multi-Turn", "count": 2},
        ],
        executors=[
            {"executor": "alice@example.com", "count": 20},
            {"executor": "bob@example.com", "count": 14},
        ],
    )

    from rhesis.sdk.entities.test_run import TestRuns

    stats = TestRuns.stats(top=1)

    assert len(stats.most_run_test_sets) == 1
    assert stats.most_run_test_sets[0].test_set_name == "Safety Evaluation"
    assert len(stats.top_executors) == 1
    assert stats.top_executors[0].executor_name == "alice@example.com"


def test_test_runs_stats_results_mode_raises():
    """result_distribution counted test_result rows within matching runs -- a
    different grain than test_run's own status. Reproducing it needs a second
    query against entity=test_result, so it's no longer done transparently."""
    from rhesis.sdk.entities.test_run import TestRuns

    with pytest.raises(NotImplementedError, match="test_result"):
        TestRuns.stats(mode="results")


def test_test_runs_stats_summary_mode_raises():
    from rhesis.sdk.entities.test_run import TestRuns

    with pytest.raises(NotImplementedError, match="summary"):
        TestRuns.stats(mode="summary")


# ---------------------------------------------------------------------------
# TestRun.stats() (instance method)
# ---------------------------------------------------------------------------


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_run_instance_stats_delegates(mock_insights_cls):
    mock_insights_cls.return_value.get.return_value = _get_response(rows=[])

    from rhesis.sdk.entities.test_run import TestRun

    run = TestRun(id="run-abc")
    stats = run.stats(mode="status", months=3)

    _, kwargs = mock_insights_cls.call_args
    assert kwargs["filters"]["test_run_ids"] == ["run-abc"]
    assert kwargs["months"] == 3
    assert stats.metadata is not None


def test_test_run_instance_stats_raises_without_id():
    from rhesis.sdk.entities.test_run import TestRun

    run = TestRun(name="No ID Run")
    with pytest.raises(ValueError, match="Test run ID is required"):
        run.stats()


# ---------------------------------------------------------------------------
# TestResults.stats()
# ---------------------------------------------------------------------------


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_results_stats_queries_five_sections_regardless_of_mode(mock_insights_cls):
    """mode is no longer a section filter -- it only ends up in metadata.mode."""
    _mock_test_result_insights(
        mock_insights_cls,
        overall={"count": 100, "passed": 80, "failed": 20, "pass_rate": 80.0},
    )

    from rhesis.sdk.entities.test_result import TestResults

    stats = TestResults.stats(mode="summary", months=6)

    assert mock_insights_cls.return_value.get.call_count == 5
    group_bys = [kwargs.get("group_by", []) for _, kwargs in mock_insights_cls.call_args_list[:5]]
    assert group_bys == [[], ["behavior"], ["category"], ["topic"], ["metric_name"]]
    assert stats.overall_pass_rates.total == 100
    assert stats.overall_pass_rates.pass_rate == 80.0
    assert stats.metadata.mode == "summary"


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_results_stats_topic_mode(mock_insights_cls):
    _mock_test_result_insights(
        mock_insights_cls,
        topic=[
            {"topic": "Safety", "count": 50, "passed": 40, "failed": 10, "pass_rate": 80.0},
            {"topic": "Accuracy", "count": 30, "passed": 25, "failed": 5, "pass_rate": 83.33},
        ],
    )

    from rhesis.sdk.entities.stats import TestResultStatsMode
    from rhesis.sdk.entities.test_result import TestResults

    stats = TestResults.stats(mode=TestResultStatsMode.TOPIC)

    assert "Safety" in stats.topic_pass_rates
    assert stats.topic_pass_rates["Safety"].pass_rate == 80.0


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_results_stats_metric_pass_rates(mock_insights_cls):
    """metrics is its own entity=metric query, grouped by metric_name."""
    _mock_test_result_insights(
        mock_insights_cls,
        metric=[
            {
                "metric_name": "Faithfulness",
                "count": 20,
                "passed": 18,
                "failed": 2,
                "pass_rate": 90.0,
            },
        ],
    )

    from rhesis.sdk.entities.test_result import TestResults

    stats = TestResults.stats(mode="metrics")

    metric_call = mock_insights_cls.call_args_list[4]
    assert metric_call.kwargs["entity"] == "metric"
    assert metric_call.kwargs["group_by"] == ["metric_name"]
    assert stats.metric_pass_rates["Faithfulness"].pass_rate == 90.0
    assert stats.metadata.available_metrics == ["Faithfulness"]


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_results_stats_ids_mode(mock_insights_cls):
    """ids is a single Insights(...).ids() call, folded into the default set."""
    _mock_test_result_insights(mock_insights_cls, ids=["tr-1", "tr-2"])

    from rhesis.sdk.entities.test_result import TestResults

    stats = TestResults.stats(mode="ids", behavior_ids=["b1"])

    mock_insights_cls.return_value.ids.assert_called_once_with(outcome="all")
    assert stats.test_ids == ["tr-1", "tr-2"]


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_results_stats_metadata_run_count_from_filters(mock_insights_cls):
    """total_test_runs/test_run_id are derived from the test_run_ids filter --
    no extra query, so they're 0/None when the call isn't scoped to specific runs."""
    from rhesis.sdk.entities.test_result import TestResults

    _mock_test_result_insights(mock_insights_cls)
    unscoped = TestResults.stats()
    assert unscoped.metadata.total_test_runs == 0
    assert unscoped.metadata.test_run_id is None

    _mock_test_result_insights(mock_insights_cls)
    single_run = TestResults.stats(test_run_id="run-1")
    assert single_run.metadata.total_test_runs == 1
    assert single_run.metadata.test_run_id == "run-1"

    _mock_test_result_insights(mock_insights_cls)
    multi_run = TestResults.stats(test_run_ids=["run-1", "run-2"])
    assert multi_run.metadata.total_test_runs == 2
    assert multi_run.metadata.test_run_id is None


@patch("rhesis.sdk.entities.stats.Insights")
def test_test_results_stats_passes_filters(mock_insights_cls):
    _mock_test_result_insights(mock_insights_cls)

    from rhesis.sdk.entities.test_result import TestResults

    TestResults.stats(
        topic_ids=["t1", "t2"],
        behavior_ids=["b1"],
        tags=["safety"],
    )

    for _, kwargs in mock_insights_cls.call_args_list:
        assert kwargs["filters"] == {
            "topic_ids": ["t1", "t2"],
            "behavior_ids": ["b1"],
            "tags": ["safety"],
        }


def test_test_results_stats_priority_filter_raises():
    from rhesis.sdk.entities.test_result import TestResults

    with pytest.raises(ValueError, match="priority_min"):
        TestResults.stats(mode="summary", priority_min=1)


@pytest.mark.parametrize("mode", ["timeline", "test_runs", "behavior_detail"])
def test_test_results_stats_other_unsupported_modes_raise(mode):
    """Each of these joins test_result-grain and metric-grain data at a grain
    Insights doesn't return in one call, so they're not reproduced here."""
    from rhesis.sdk.entities.test_result import TestResults

    with pytest.raises(NotImplementedError, match="Insights"):
        TestResults.stats(mode=mode)


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
