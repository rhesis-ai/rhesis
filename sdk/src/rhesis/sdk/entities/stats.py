"""Statistics models and enums for test run and test result analytics."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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
    OVERALL = "overall"
    TIMELINE = "timeline"
    TEST_RUNS = "test_runs"


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
    result_breakdown: Dict[str, int] = {}


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
    available_statuses: List[str] = []
    available_test_sets: List[str] = []
    available_executors: List[str] = []


# ---------------------------------------------------------------------------
# Test Result Stats models
# ---------------------------------------------------------------------------


class TimelineData(BaseModel):
    date: str
    overall: OverallStats = OverallStats()
    metrics: Dict[str, MetricStats] = {}


class TestRunSummary(BaseModel):
    id: str
    name: str
    created_at: Optional[str] = None
    total_tests: int = 0
    overall: OverallStats = OverallStats()
    metrics: Dict[str, MetricStats] = {}


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
    available_metrics: List[str] = []
    available_behaviors: List[str] = []
    available_categories: List[str] = []
    available_topics: List[str] = []


# ---------------------------------------------------------------------------
# DataFrame helper
# ---------------------------------------------------------------------------


def _to_dataframe(data: Any, section: str):
    """Convert a stats section to a pandas DataFrame.

    Raises ImportError with install instructions if pandas is not available.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for to_dataframe(). "
            "Install it with: pip install pandas"
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
    """Response from ``TestRuns.stats()``.

    All data fields are optional because the ``mode`` parameter controls
    which sections the backend populates.
    """

    status_distribution: Optional[List[StatusDistribution]] = None
    result_distribution: Optional[ResultDistribution] = None
    most_run_test_sets: Optional[List[TestSetRunCount]] = None
    top_executors: Optional[List[ExecutorRunCount]] = None
    timeline: Optional[List[TestRunTimelineData]] = None
    overall_summary: Optional[TestRunOverallSummary] = None
    metadata: Optional[TestRunStatsMetadata] = None

    def to_dataframe(self, section: str):
        """Convert a named section to a pandas DataFrame.

        Args:
            section: Field name such as ``"status_distribution"``,
                ``"timeline"``, ``"most_run_test_sets"``, etc.

        Returns:
            A ``pandas.DataFrame`` built from the section data.

        Raises:
            ImportError: If pandas is not installed.
            ValueError: If the section cannot be converted.
            AttributeError: If the section name is invalid.
        """
        return _to_dataframe(getattr(self, section), section)


class TestResultStats(BaseModel):
    """Response from ``TestResults.stats()``.

    All data fields are optional because the ``mode`` parameter controls
    which sections the backend populates.
    """

    metric_pass_rates: Optional[Dict[str, MetricStats]] = None
    behavior_pass_rates: Optional[Dict[str, MetricStats]] = None
    category_pass_rates: Optional[Dict[str, MetricStats]] = None
    topic_pass_rates: Optional[Dict[str, MetricStats]] = None
    overall_pass_rates: Optional[OverallStats] = None
    timeline: Optional[List[TimelineData]] = None
    test_run_summary: Optional[List[TestRunSummary]] = None
    metadata: Optional[TestResultStatsMetadata] = None

    def to_dataframe(self, section: str):
        """Convert a named section to a pandas DataFrame.

        Args:
            section: Field name such as ``"topic_pass_rates"``,
                ``"timeline"``, ``"metric_pass_rates"``, etc.

        Returns:
            A ``pandas.DataFrame`` built from the section data.

        Raises:
            ImportError: If pandas is not installed.
            ValueError: If the section cannot be converted.
            AttributeError: If the section name is invalid.
        """
        return _to_dataframe(getattr(self, section), section)
