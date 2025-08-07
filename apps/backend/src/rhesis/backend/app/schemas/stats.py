from typing import Dict, List, Optional, Union
from datetime import datetime

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

# Backward compatibility alias
TestResultStats = TestResultStatsAll
