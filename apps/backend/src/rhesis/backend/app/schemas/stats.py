from typing import Dict, List, Optional, Union

from pydantic import BaseModel


# Legacy schemas for backward compatibility
class DimensionStats(BaseModel):
    dimension: str
    total: int
    breakdown: Dict[str, int]


class HistoricalStats(BaseModel):
    period: str
    start_date: str
    end_date: str
    monthly_counts: Dict[str, int]


class EntityStats(BaseModel):
    total: int
    stats: Dict[str, DimensionStats]
    metadata: Optional[Dict] = None
    history: Optional[HistoricalStats] = None


# Test Result Stats Schemas
class MetricStats(BaseModel):
    total: int
    passed: int
    failed: int
    pass_rate: float


class OverallStats(BaseModel):
    total: int
    passed: int
    failed: int
    pass_rate: float


class TimelineData(BaseModel):
    date: str
    overall: OverallStats
    metrics: Dict[str, MetricStats]


class TestRunSummary(BaseModel):
    id: str
    name: str
    created_at: Optional[str] = None
    total_tests: int
    overall: OverallStats
    metrics: Dict[str, MetricStats]


class TestResultStatsMetadata(BaseModel):
    generated_at: str
    organization_id: Optional[str] = None
    test_run_id: Optional[str] = None
    period: str
    start_date: str
    end_date: str
    total_test_runs: int
    total_test_results: int
    mode: str
    available_metrics: List[str]
    available_behaviors: List[str]
    available_categories: List[str]
    available_topics: List[str]


# Mode-specific response schemas
class TestResultStatsAll(BaseModel):
    """Complete dataset - all sections"""

    metric_pass_rates: Dict[str, MetricStats]
    behavior_pass_rates: Dict[str, MetricStats]
    category_pass_rates: Dict[str, MetricStats]
    topic_pass_rates: Dict[str, MetricStats]
    overall_pass_rates: OverallStats
    timeline: List[TimelineData]
    test_run_summary: List[TestRunSummary]
    metadata: TestResultStatsMetadata


class TestResultStatsSummary(BaseModel):
    """Lightweight summary - overall stats + metadata only"""

    overall_pass_rates: OverallStats
    metadata: TestResultStatsMetadata


class TestResultStatsMetrics(BaseModel):
    """Individual metric pass/fail rates only"""

    metric_pass_rates: Dict[str, MetricStats]
    metadata: TestResultStatsMetadata


class TestResultStatsBehavior(BaseModel):
    """Behavior pass/fail rates only"""

    behavior_pass_rates: Dict[str, MetricStats]
    metadata: TestResultStatsMetadata


class TestResultStatsCategory(BaseModel):
    """Category pass/fail rates only"""

    category_pass_rates: Dict[str, MetricStats]
    metadata: TestResultStatsMetadata


class TestResultStatsTopic(BaseModel):
    """Topic pass/fail rates only"""

    topic_pass_rates: Dict[str, MetricStats]
    metadata: TestResultStatsMetadata


class TestResultStatsOverall(BaseModel):
    """Overall pass/fail rates only"""

    overall_pass_rates: OverallStats
    metadata: TestResultStatsMetadata


class TestResultStatsTimeline(BaseModel):
    """Timeline data only"""

    timeline: List[TimelineData]
    metadata: TestResultStatsMetadata


class TestResultStatsTestRuns(BaseModel):
    """Test run summary only"""

    test_run_summary: List[TestRunSummary]
    metadata: TestResultStatsMetadata


# Union type for all possible responses
TestResultStatsResponse = Union[
    TestResultStatsAll,
    TestResultStatsSummary,
    TestResultStatsMetrics,
    TestResultStatsBehavior,
    TestResultStatsCategory,
    TestResultStatsTopic,
    TestResultStatsOverall,
    TestResultStatsTimeline,
    TestResultStatsTestRuns,
]


# Test Run Stats Schemas
class StatusDistribution(BaseModel):
    status: str
    count: int
    percentage: float


class ResultDistribution(BaseModel):
    total: int
    passed: int
    failed: int
    pending: int
    pass_rate: float


class TestSetRunCount(BaseModel):
    test_set_name: str
    run_count: int


class ExecutorRunCount(BaseModel):
    executor_name: str
    run_count: int


class TestRunTimelineData(BaseModel):
    date: str
    total_runs: int
    status_breakdown: Dict[str, int]
    result_breakdown: Dict[str, int]


class TestRunOverallSummary(BaseModel):
    total_runs: int
    unique_test_sets: int
    unique_executors: int
    most_common_status: str
    pass_rate: float


class TestRunStatsMetadata(BaseModel):
    generated_at: str
    organization_id: Optional[str] = None
    period: str
    start_date: str
    end_date: str
    total_test_runs: int
    mode: str
    available_statuses: List[str]
    available_test_sets: List[str]
    available_executors: List[str]


# Mode-specific test run response schemas
class TestRunStatsAll(BaseModel):
    """Complete dataset - all sections"""

    status_distribution: List[StatusDistribution]
    result_distribution: ResultDistribution
    most_run_test_sets: List[TestSetRunCount]
    top_executors: List[ExecutorRunCount]
    timeline: List[TestRunTimelineData]
    overall_summary: TestRunOverallSummary
    metadata: TestRunStatsMetadata


class TestRunStatsSummary(BaseModel):
    """Lightweight summary - overall summary + metadata only"""

    overall_summary: TestRunOverallSummary
    metadata: TestRunStatsMetadata


class TestRunStatsStatus(BaseModel):
    """Status distribution only"""

    status_distribution: List[StatusDistribution]
    metadata: TestRunStatsMetadata


class TestRunStatsResults(BaseModel):
    """Result distribution only"""

    result_distribution: ResultDistribution
    metadata: TestRunStatsMetadata


class TestRunStatsTests(BaseModel):
    """Most run test sets only"""

    most_run_test_sets: List[TestSetRunCount]
    metadata: TestRunStatsMetadata


class TestRunStatsExecutors(BaseModel):
    """Top executors only"""

    top_executors: List[ExecutorRunCount]
    metadata: TestRunStatsMetadata


class TestRunStatsTimeline(BaseModel):
    """Timeline data only"""

    timeline: List[TestRunTimelineData]
    metadata: TestRunStatsMetadata


# Union type for all possible test run responses
TestRunStatsResponse = Union[
    TestRunStatsAll,
    TestRunStatsSummary,
    TestRunStatsStatus,
    TestRunStatsResults,
    TestRunStatsTests,
    TestRunStatsExecutors,
    TestRunStatsTimeline,
]


# Backward compatibility alias
TestResultStats = TestResultStatsAll
