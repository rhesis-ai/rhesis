"""Statistics models and enums for test run and test result analytics."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rhesis.sdk.entities.insights import Insights

# ---------------------------------------------------------------------------
# Mode enums (str subclass so they pass directly as query param strings)
# ---------------------------------------------------------------------------


class TestRunStatsMode(str, Enum):
    ALL = "all"
    SUMMARY = "summary"
    STATUS = "status"
    RESULTS = "results"
    TEST_SETS = "test_sets"
    EXECUTORS = "executors"
    TIMELINE = "timeline"


class TestResultStatsMode(str, Enum):
    ALL = "all"
    SUMMARY = "summary"
    METRICS = "metrics"
    BEHAVIOR = "behavior"
    CATEGORY = "category"
    TOPIC = "topic"
    TIMELINE = "timeline"
    TEST_RUNS = "test_runs"
    IDS = "ids"
    BEHAVIOR_DETAIL = "behavior_detail"


# ---------------------------------------------------------------------------
# Shared nested models
# ---------------------------------------------------------------------------


class MetricStats(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0


class OverallStats(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0


# ---------------------------------------------------------------------------
# Test Run Stats models
# ---------------------------------------------------------------------------


class StatusDistribution(BaseModel):
    status: str
    count: int
    percentage: float = 0.0


class ResultDistribution(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    pending: int = 0
    pass_rate: float = 0.0


class TestSetRunCount(BaseModel):
    test_set_name: str
    run_count: int


class ExecutorRunCount(BaseModel):
    executor_name: str
    run_count: int


class TestRunTimelineData(BaseModel):
    date: str
    total_runs: int = 0
    result_breakdown: Dict[str, int] = Field(default_factory=dict)


class TestRunOverallSummary(BaseModel):
    total_runs: int = 0
    unique_test_sets: int = 0
    unique_executors: int = 0
    most_common_status: str = ""
    pass_rate: float = 0.0


class TestRunStatsMetadata(BaseModel):
    generated_at: str = ""
    organization_id: Optional[str] = None
    period: str = ""
    start_date: str = ""
    end_date: str = ""
    total_test_runs: int = 0
    mode: str = ""
    available_statuses: List[str] = Field(default_factory=list)
    available_test_sets: List[str] = Field(default_factory=list)
    available_executors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Test Result Stats models
# ---------------------------------------------------------------------------


class TimelineData(BaseModel):
    date: str
    overall: OverallStats = Field(default_factory=OverallStats)
    metrics: Dict[str, MetricStats] = Field(default_factory=dict)


class TestRunSummary(BaseModel):
    id: str
    name: str
    created_at: Optional[str] = None
    total_tests: int = 0
    overall: OverallStats = Field(default_factory=OverallStats)
    metrics: Dict[str, MetricStats] = Field(default_factory=dict)


class BehaviorDetail(BaseModel):
    overall_pass_rates: OverallStats = Field(default_factory=OverallStats)
    metric_pass_rates: Dict[str, MetricStats] = Field(default_factory=dict)
    topic_pass_rates: Dict[str, MetricStats] = Field(default_factory=dict)


class TestResultStatsMetadata(BaseModel):
    generated_at: str = ""
    organization_id: Optional[str] = None
    test_run_id: Optional[str] = None
    period: str = ""
    start_date: str = ""
    end_date: str = ""
    total_test_runs: int = 0
    total_test_results: int = 0
    mode: str = ""
    available_metrics: List[str] = Field(default_factory=list)
    available_behaviors: List[str] = Field(default_factory=list)
    available_categories: List[str] = Field(default_factory=list)
    available_topics: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# DataFrame helper
# ---------------------------------------------------------------------------


def _to_dataframe(data: Any, section: str):
    """Convert a stats section to a DataFrame; raises ImportError if pandas isn't installed."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for to_dataframe(). Install it with: pip install pandas"
        )

    if data is None:
        return pd.DataFrame()

    if isinstance(data, list):
        rows = [item.model_dump() if isinstance(item, BaseModel) else item for item in data]
        return pd.DataFrame(rows)

    if isinstance(data, dict):
        rows = {}
        for key, val in data.items():
            rows[key] = val.model_dump() if isinstance(val, BaseModel) else val
        return pd.DataFrame.from_dict(rows, orient="index")

    if isinstance(data, BaseModel):
        return pd.DataFrame([data.model_dump()])

    raise ValueError(f"Cannot convert section '{section}' to DataFrame")


# ---------------------------------------------------------------------------
# Top-level response models
# ---------------------------------------------------------------------------


class TestRunStats(BaseModel):
    """Response from ``TestRuns.stats()``. All fields are optional: only
    status_distribution/most_run_test_sets/top_executors/timeline/metadata are
    ever populated -- the rest predate the Insights-backed builder above."""

    status_distribution: Optional[List[StatusDistribution]] = None
    result_distribution: Optional[ResultDistribution] = None
    most_run_test_sets: Optional[List[TestSetRunCount]] = None
    top_executors: Optional[List[ExecutorRunCount]] = None
    timeline: Optional[List[TestRunTimelineData]] = None
    overall_summary: Optional[TestRunOverallSummary] = None
    metadata: Optional[TestRunStatsMetadata] = None

    def to_dataframe(self, section: str):
        """Convert a named section (e.g. ``"timeline"``) to a pandas DataFrame."""
        return _to_dataframe(getattr(self, section), section)


# ---------------------------------------------------------------------------
# Insights-backed builders. TestResults.stats() / TestRuns.stats() build
# Insights() queries and reshape the rows into the models above -- mode only
# ends up in metadata.mode, and legacy modes that need a second, different-
# grain query raise NotImplementedError.
# ---------------------------------------------------------------------------


def _period_label(months: Optional[int], start_date: Optional[str], end_date: Optional[str]) -> str:
    if months is not None:
        return f"Last {months} months"
    if start_date or end_date:
        return "custom"
    return "all time"


# ---- test_result section builders -----------------------------------------
#
# timeline/test_runs/behavior_detail joined test_result-grain and metric-grain
# data in SQL at a grain Insights doesn't offer in one call -- not worth
# reproducing here. metrics is its own entity="metric" query and ids is a
# single Insights(...).ids() call -- both folded into the default set below.


def _tr_overall(filters, months, start_date, end_date) -> OverallStats:
    resp = Insights(
        entity="test_result",
        measures=["count", "passed", "failed", "pass_rate"],
        filters=filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).get()
    if not resp.rows:
        return OverallStats()
    row = resp.rows[0]
    return OverallStats(
        total=row["count"], passed=row["passed"], failed=row["failed"], pass_rate=row["pass_rate"]
    )


def _tr_dimension(dimension: str, filters, months, start_date, end_date) -> Dict[str, MetricStats]:
    """Pass/fail rates grouped by a test_result dimension (behavior/category/topic)."""
    resp = Insights(
        entity="test_result",
        group_by=[dimension],
        measures=["count", "passed", "failed", "pass_rate"],
        filters=filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).get()
    return {
        row[dimension]: MetricStats(
            total=row["count"],
            passed=row["passed"],
            failed=row["failed"],
            pass_rate=row["pass_rate"],
        )
        for row in resp.rows
        if row[dimension] is not None
    }


_METRIC_ENTITY_FILTER_KEYS = frozenset({"test_run_ids", "behavior_ids", "test_ids", "metric_names"})


def _tr_metric(filters, months, start_date, end_date) -> Dict[str, MetricStats]:
    """Pass/fail rates grouped by metric name (entity=metric, not test_result)."""
    metric_filters = {k: v for k, v in filters.items() if k in _METRIC_ENTITY_FILTER_KEYS}
    resp = Insights(
        entity="metric",
        group_by=["metric_name"],
        measures=["count", "passed", "failed", "pass_rate"],
        filters=metric_filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).get()
    return {
        row["metric_name"]: MetricStats(
            total=row["count"],
            passed=row["passed"],
            failed=row["failed"],
            pass_rate=row["pass_rate"],
        )
        for row in resp.rows
        if row["metric_name"] is not None
    }


def _tr_ids(filters, months, start_date, end_date) -> List[str]:
    resp = Insights(
        entity="test_result",
        filters=filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).ids(outcome="all")
    return resp.ids


_UNSUPPORTED_TEST_RESULT_MODES = frozenset({"timeline", "test_runs", "behavior_detail"})


def build_test_result_stats(
    mode,
    filters: Dict[str, List[str]],
    months: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> "TestResultStats":
    """Query Insights for overall/behavior/category/topic/metric pass rates and
    matching test IDs, and shape them into TestResultStats. Raises for modes in
    _UNSUPPORTED_TEST_RESULT_MODES."""
    mode = mode.value if isinstance(mode, Enum) else mode
    if mode in _UNSUPPORTED_TEST_RESULT_MODES:
        raise NotImplementedError(
            f"TestResults.stats(mode={mode!r}) is no longer supported. Call "
            'Insights(entity="test_result", ...) or Insights(entity="metric", ...) '
            "directly instead -- see docs/content/sdk/statistics.mdx."
        )

    overall = _tr_overall(filters, months, start_date, end_date)
    behavior = _tr_dimension("behavior", filters, months, start_date, end_date)
    category = _tr_dimension("category", filters, months, start_date, end_date)
    topic = _tr_dimension("topic", filters, months, start_date, end_date)
    metric = _tr_metric(filters, months, start_date, end_date)
    test_ids = _tr_ids(filters, months, start_date, end_date)
    run_ids = filters.get("test_run_ids") or []

    metadata = TestResultStatsMetadata(
        generated_at=datetime.now(timezone.utc).isoformat(),
        period=_period_label(months, start_date, end_date),
        start_date=start_date or "",
        end_date=end_date or "",
        total_test_results=overall.total,
        total_test_runs=len(run_ids),
        test_run_id=run_ids[0] if len(run_ids) == 1 else None,
        mode=mode,
        available_behaviors=sorted(behavior),
        available_categories=sorted(category),
        available_topics=sorted(topic),
        available_metrics=sorted(metric),
    )
    return TestResultStats(
        overall_pass_rates=overall,
        behavior_pass_rates=behavior,
        category_pass_rates=category,
        topic_pass_rates=topic,
        metric_pass_rates=metric,
        test_ids=test_ids,
        metadata=metadata,
    )


# ---- test_run section builders ---------------------------------------------


def _run_status(filters, months, start_date, end_date) -> List[StatusDistribution]:
    resp = Insights(
        entity="test_run",
        group_by=["status"],
        measures=["count"],
        filters=filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).get()
    rows = [(row["status"], row["count"]) for row in resp.rows if row["status"] is not None]
    total = sum(count for _, count in rows)
    return [
        StatusDistribution(
            status=name, count=count, percentage=round((count / total) * 100, 2) if total else 0.0
        )
        for name, count in sorted(rows, key=lambda r: r[1], reverse=True)
    ]


def _run_test_sets(filters, months, start_date, end_date, top=None) -> List[TestSetRunCount]:
    resp = Insights(
        entity="test_run",
        group_by=["test_set"],
        measures=["count"],
        filters=filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).get()
    rows = sorted(
        (row for row in resp.rows if row["test_set"] is not None),
        key=lambda r: r["count"],
        reverse=True,
    )
    if top:
        rows = rows[:top]
    return [TestSetRunCount(test_set_name=row["test_set"], run_count=row["count"]) for row in rows]


def _run_executors(filters, months, start_date, end_date, top=None) -> List[ExecutorRunCount]:
    resp = Insights(
        entity="test_run",
        group_by=["executor"],
        measures=["count"],
        filters=filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).get()
    rows = sorted(
        (row for row in resp.rows if row["executor"] is not None),
        key=lambda r: r["count"],
        reverse=True,
    )
    if top:
        rows = rows[:top]
    return [ExecutorRunCount(executor_name=row["executor"], run_count=row["count"]) for row in rows]


def _run_timeline(filters, months, start_date, end_date) -> List[TestRunTimelineData]:
    resp = Insights(
        entity="test_run",
        group_by=["year", "month"],
        measures=["count", "passed", "failed"],
        filters=filters,
        months=months,
        start_date=start_date,
        end_date=end_date,
    ).get()
    timeline = []
    for row in resp.rows:
        if row["year"] is None or row["month"] is None:
            continue
        total, passed, failed = row["count"], row["passed"], row["failed"]
        timeline.append(
            TestRunTimelineData(
                date=f"{row['year']:04d}-{row['month']:02d}",
                total_runs=total,
                result_breakdown={
                    "passed": passed,
                    "failed": failed,
                    "other": total - passed - failed,
                },
            )
        )
    return sorted(timeline, key=lambda t: t.date)


_UNSUPPORTED_TEST_RUN_MODES = frozenset({"results", "summary"})


def build_test_run_stats(
    mode,
    filters: Dict[str, List[str]],
    months: Optional[int],
    top: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> "TestRunStats":
    """Query Insights for status/test_set/executor/timeline breakdowns and shape
    them into TestRunStats. Raises for modes in _UNSUPPORTED_TEST_RUN_MODES."""
    mode = mode.value if isinstance(mode, Enum) else mode
    if mode in _UNSUPPORTED_TEST_RUN_MODES:
        raise NotImplementedError(
            f"TestRuns.stats(mode={mode!r}) is no longer supported. Call "
            'Insights(entity="test_run", ...) directly, combined with a second '
            'Insights(entity="test_result", ...) query for result-level detail -- '
            "see docs/content/sdk/statistics.mdx."
        )

    status = _run_status(filters, months, start_date, end_date)
    test_sets = _run_test_sets(filters, months, start_date, end_date, top=top)
    executors = _run_executors(filters, months, start_date, end_date, top=top)
    timeline = _run_timeline(filters, months, start_date, end_date)

    metadata = TestRunStatsMetadata(
        generated_at=datetime.now(timezone.utc).isoformat(),
        period=_period_label(months, start_date, end_date),
        start_date=start_date or "",
        end_date=end_date or "",
        total_test_runs=sum(s.count for s in status),
        mode=mode,
        available_statuses=[s.status for s in status],
        available_test_sets=[t.test_set_name for t in test_sets],
        available_executors=[e.executor_name for e in executors],
    )
    return TestRunStats(
        status_distribution=status,
        most_run_test_sets=test_sets,
        top_executors=executors,
        timeline=timeline,
        metadata=metadata,
    )


class TestResultStats(BaseModel):
    """Response from ``TestResults.stats()``. All fields are optional: only
    overall_pass_rates/behavior_pass_rates/category_pass_rates/topic_pass_rates/
    metric_pass_rates/test_ids/metadata are ever populated -- the rest predate
    the Insights-backed builder above."""

    metric_pass_rates: Optional[Dict[str, MetricStats]] = None
    behavior_pass_rates: Optional[Dict[str, MetricStats]] = None
    category_pass_rates: Optional[Dict[str, MetricStats]] = None
    topic_pass_rates: Optional[Dict[str, MetricStats]] = None
    overall_pass_rates: Optional[OverallStats] = None
    timeline: Optional[List[TimelineData]] = None
    test_run_summary: Optional[List[TestRunSummary]] = None
    test_ids: Optional[List[str]] = None
    behavior_detail: Optional[Dict[str, BehaviorDetail]] = None
    metadata: Optional[TestResultStatsMetadata] = None

    def to_dataframe(self, section: str):
        """Convert a named section (e.g. ``"topic_pass_rates"``) to a pandas DataFrame."""
        return _to_dataframe(getattr(self, section), section)
