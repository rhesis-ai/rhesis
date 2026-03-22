"""Integration tests for SDK stats API.

These tests hit the real backend via Docker and verify response shapes.
Stats may return empty results depending on seed data -- the tests verify
the response structure and types, not specific counts.
"""

import pytest

from rhesis.sdk.entities.stats import (
    TestResultStats,
    TestResultStatsMode,
    TestRunStats,
    TestRunStatsMode,
)
from rhesis.sdk.entities.test_result import TestResults
from rhesis.sdk.entities.test_run import TestRuns


# ---------------------------------------------------------------------------
# TestRuns.stats()
# ---------------------------------------------------------------------------


def test_test_runs_stats_all(docker_compose_test_env):
    stats = TestRuns.stats(mode=TestRunStatsMode.ALL, months=6)

    assert isinstance(stats, TestRunStats)
    assert stats.metadata is not None
    assert stats.metadata.mode == "all"
    assert isinstance(stats.metadata.total_test_runs, int)


def test_test_runs_stats_status_mode(docker_compose_test_env):
    stats = TestRuns.stats(mode=TestRunStatsMode.STATUS)

    assert isinstance(stats, TestRunStats)
    assert stats.metadata is not None
    assert stats.metadata.mode == "status"
    if stats.status_distribution is not None:
        for item in stats.status_distribution:
            assert hasattr(item, "status")
            assert hasattr(item, "count")


def test_test_runs_stats_summary_mode(docker_compose_test_env):
    stats = TestRuns.stats(mode=TestRunStatsMode.SUMMARY)

    assert isinstance(stats, TestRunStats)
    assert stats.metadata is not None
    assert stats.metadata.mode == "summary"


def test_test_runs_stats_with_months_filter(docker_compose_test_env):
    stats = TestRuns.stats(mode=TestRunStatsMode.SUMMARY, months=1)

    assert isinstance(stats, TestRunStats)
    assert stats.metadata is not None
    assert "1 month" in stats.metadata.period.lower() or "last" in stats.metadata.period.lower()


def test_test_runs_stats_with_string_mode(docker_compose_test_env):
    stats = TestRuns.stats(mode="all", months=6)

    assert isinstance(stats, TestRunStats)
    assert stats.metadata is not None


# ---------------------------------------------------------------------------
# TestResults.stats()
# ---------------------------------------------------------------------------


def test_test_results_stats_all(docker_compose_test_env):
    stats = TestResults.stats(mode=TestResultStatsMode.ALL, months=6)

    assert isinstance(stats, TestResultStats)
    assert stats.metadata is not None
    assert stats.metadata.mode == "all"
    assert isinstance(stats.metadata.total_test_results, int)


def test_test_results_stats_topic_mode(docker_compose_test_env):
    stats = TestResults.stats(mode=TestResultStatsMode.TOPIC)

    assert isinstance(stats, TestResultStats)
    assert stats.metadata is not None
    assert stats.metadata.mode == "topic"
    if stats.topic_pass_rates is not None:
        for name, metric in stats.topic_pass_rates.items():
            assert isinstance(name, str)
            assert hasattr(metric, "total")
            assert hasattr(metric, "pass_rate")


def test_test_results_stats_behavior_mode(docker_compose_test_env):
    stats = TestResults.stats(mode=TestResultStatsMode.BEHAVIOR)

    assert isinstance(stats, TestResultStats)
    assert stats.metadata is not None
    assert stats.metadata.mode == "behavior"


def test_test_results_stats_summary_mode(docker_compose_test_env):
    stats = TestResults.stats(mode=TestResultStatsMode.SUMMARY)

    assert isinstance(stats, TestResultStats)
    assert stats.metadata is not None
    assert stats.metadata.mode == "summary"


def test_test_results_stats_with_string_mode(docker_compose_test_env):
    stats = TestResults.stats(mode="metrics", months=3)

    assert isinstance(stats, TestResultStats)
    assert stats.metadata is not None
