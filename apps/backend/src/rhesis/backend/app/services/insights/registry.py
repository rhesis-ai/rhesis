"""Declarative registry of what Insights endpoints can query.

Each entity names the view backing it, the dimensions it can be grouped by,
the measures computable over it, and the filters it accepts. query_builder.py
validates every incoming param against this before touching the database, and
GET /insights/schema serves it as-is, so a description written here is what
the Architect and MCP clients read.

A dimension with an `id` column groups by that id and returns both keys in
each row (`topic` and `topic_id`), so two entities sharing a name stay apart.

An entity with a `source` is built per query instead of read from a view. Its
dimensions, filters and date column name source columns as strings, and its
measures take the source's column collection.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from sqlalchemy import Float, Integer, Numeric, case, cast, func

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.models.stats_views import (
    MetricStatsView,
    TestResultStatsView,
    TestRunStatsView,
    TestStatsView,
)
from rhesis.backend.app.models.tag import Tag, TaggedItem
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services.insights.trace_source import trace_stats

TR = TestResultStatsView
RN = TestRunStatsView
ME = MetricStatsView
TS = TestStatsView

PERIOD = "period"
TIME_GRAINS = ("day", "week", "month", "quarter", "year")
DEFAULT_TIME_GRAIN = "month"


@dataclass(frozen=True)
class Dimension:
    name: Any
    description: str
    id: Optional[Any] = None


@dataclass(frozen=True)
class Measure:
    build: Callable[..., Any]
    kind: str  # "count", "rate" (0-100), "score" (0-1), "duration" (ms) or "currency" (USD)
    description: str


@dataclass(frozen=True)
class Filter:
    column: Any
    description: str
    # (db, values) -> query of ids that `column` must be in, for relationships the
    # view can't flatten into a plain column (many-to-many test sets, polymorphic tags).
    subquery: Optional[Callable] = None


@dataclass(frozen=True)
class Entity:
    view: Any
    description: str
    date_column: Any
    dimensions: Dict[str, Dimension]
    measures: Dict[str, Measure]
    filters: Dict[str, Filter]
    # GET /insights/ids only: the column to SELECT DISTINCT, and the
    # (view, 'pass'|'fail') -> predicate behind its outcome param.
    id_column: Any = None
    apply_outcome: Optional[Callable] = None
    # (db, start_date, end_date) -> subquery, for an entity no view can express; see the
    # module docstring.
    source: Optional[Callable] = None


def _count():
    return func.count()


def _count_where(condition):
    return lambda: func.count().filter(condition)


def _sum(column):
    # SUM over bigint is numeric, which JSON-encodes as a string.
    return lambda: cast(func.sum(column), Integer)


def _rate(passed, failed):
    """passed / (passed + failed) * 100 -- pending/error rows excluded from the
    denominator.

    passed/failed are zero-arg callables so callers can pass either a row count
    (func.count().filter(...)) or a pre-aggregated sum (func.sum(...)).
    """

    def _measure():
        passed_expr = passed()
        failed_expr = failed()
        total = passed_expr + failed_expr
        rate = case((total == 0, 0), else_=passed_expr * 100.0 / total)
        # A bound 100.0 is float8, and Postgres has round(numeric, int) only.
        return cast(func.round(cast(rate, Numeric), 2), Float)

    return _measure


def _score(aggregate):
    return lambda: cast(func.round(cast(aggregate(ME.score), Numeric), 4), Float)


def _test_set_ids_subquery(db, test_set_ids):
    return db.query(test_test_set_association.c.test_id).filter(
        test_test_set_association.c.test_set_id.in_(test_set_ids)
    )


def _tags_subquery(db, tags):
    return (
        db.query(TaggedItem.entity_id)
        .join(Tag, TaggedItem.tag_id == Tag.id)
        .filter(TaggedItem.entity_type == "Test", Tag.name.in_(tags))
    )


def _overall_result_outcome(view, outcome: str):
    target = OverallTestResult.PASSED if outcome == "pass" else OverallTestResult.FAILED
    return view.result == target


def _metric_success_outcome(view, outcome: str):
    return view.effective_success.is_(outcome == "pass")


_PASSED = TR.result == OverallTestResult.PASSED
_FAILED = TR.result == OverallTestResult.FAILED


def _trace_rate(c):
    rate = case((func.count() == 0, 0), else_=func.sum(c.error_flag) * 100.0 / func.count())
    return cast(func.round(cast(rate, Numeric), 2), Float)


def _trace_percentile(fraction):
    return lambda c: cast(
        func.round(cast(func.percentile_cont(fraction).within_group(c.duration_ms), Numeric), 2),
        Float,
    )


def _run_duration(aggregate):
    return lambda: cast(func.round(cast(aggregate(RN.duration_ms), Numeric), 0), Float)


def _run_duration_percentile(fraction):
    return _run_duration(lambda column: func.percentile_cont(fraction).within_group(column))


def _trace_round(aggregate, column, places):
    return lambda c: cast(func.round(cast(aggregate(c[column]), Numeric), places), Float)


REGISTRY: Dict[str, Entity] = {
    "test_result": Entity(
        view=TR,
        description=(
            "One row per test execution. Use for pass rates and breakdowns of what was run: "
            "per requirement, topic, run, endpoint, over time."
        ),
        date_column=TR.created_at,
        id_column=TR.test_id,
        apply_outcome=_overall_result_outcome,
        dimensions={
            "requirement": Dimension(
                TR.requirement_name, "Requirement the test covers", TR.requirement_id
            ),
            "category": Dimension(TR.category_name, "Test category", TR.category_id),
            "topic": Dimension(TR.topic_name, "Test topic", TR.topic_id),
            "test_run": Dimension(TR.test_run_name, "Test run (by name)", TR.test_run_id),
            "test_set": Dimension(TR.test_set_name, "Test set the run executed", TR.test_set_id),
            "endpoint": Dimension(TR.endpoint_name, "Endpoint the run targeted", TR.endpoint_id),
            "executor": Dimension(TR.executor_name, "User who started the run", TR.executor_id),
            "status": Dimension(TR.status_name, "Test result status", TR.result_status_id),
            "priority": Dimension(TR.priority, "Test priority"),
        },
        measures={
            "count": Measure(_count, "count", "Number of test results"),
            "passed": Measure(_count_where(_PASSED), "count", "Results that passed"),
            "failed": Measure(_count_where(_FAILED), "count", "Results that failed"),
            "error_count": Measure(
                _count_where(TR.result == "error"), "count", "Results whose execution errored"
            ),
            "pending_count": Measure(
                _count_where(TR.result.in_(("pending", "cancelled"))),
                "count",
                "Results not run, still running, or cancelled",
            ),
            "pass_rate": Measure(
                _rate(_count_where(_PASSED), _count_where(_FAILED)),
                "rate",
                "passed / (passed + failed) x 100; errors and pending excluded",
            ),
        },
        filters={
            "requirement_ids": Filter(TR.requirement_id, "Requirement IDs"),
            "category_ids": Filter(TR.category_id, "Category IDs"),
            "topic_ids": Filter(TR.topic_id, "Topic IDs"),
            "test_run_ids": Filter(TR.test_run_id, "Test run IDs"),
            "test_set_ids": Filter(TR.test_set_id, "Test set IDs (the set the run executed)"),
            "endpoint_ids": Filter(TR.endpoint_id, "Endpoint IDs"),
            "executor_ids": Filter(TR.executor_id, "IDs of users who started the run"),
            "status_ids": Filter(TR.result_status_id, "Test result status IDs"),
            "test_ids": Filter(TR.test_id, "Test IDs"),
            "test_type_ids": Filter(TR.test_type_id, "Test type IDs"),
            "user_ids": Filter(TR.test_user_id, "IDs of users who created the test"),
            "assignee_ids": Filter(TR.assignee_id, "Test assignee user IDs"),
            "owner_ids": Filter(TR.owner_id, "Test owner user IDs"),
            "prompt_ids": Filter(TR.prompt_id, "Prompt IDs"),
            "tags": Filter(TR.test_id, "Test tag names", subquery=_tags_subquery),
        },
    ),
    "metric": Entity(
        view=ME,
        description=(
            "One row per (test result, metric). Use for per-metric pass rates and scores, "
            "and which metrics fail where."
        ),
        date_column=ME.created_at,
        id_column=ME.test_id,
        apply_outcome=_metric_success_outcome,
        dimensions={
            "metric": Dimension(ME.metric_name, "Metric name"),
            "requirement": Dimension(
                ME.requirement_name, "Requirement the test covers", ME.requirement_id
            ),
            "category": Dimension(ME.category_name, "Test category", ME.category_id),
            "topic": Dimension(ME.topic_name, "Test topic", ME.topic_id),
            "test_run": Dimension(ME.test_run_name, "Test run (by name)", ME.test_run_id),
            "test_set": Dimension(ME.test_set_name, "Test set the run executed", ME.test_set_id),
            "endpoint": Dimension(ME.endpoint_name, "Endpoint the run targeted", ME.endpoint_id),
        },
        measures={
            "count": Measure(_count, "count", "Number of metric evaluations"),
            "passed": Measure(
                _count_where(ME.effective_success.is_(True)), "count", "Evaluations that passed"
            ),
            "failed": Measure(
                _count_where(ME.effective_success.is_(False)), "count", "Evaluations that failed"
            ),
            "pass_rate": Measure(
                _rate(
                    _count_where(ME.effective_success.is_(True)),
                    _count_where(ME.effective_success.is_(False)),
                ),
                "rate",
                "passed / (passed + failed) x 100, after human overrides",
            ),
            "avg_score": Measure(_score(func.avg), "score", "Mean numeric score"),
            "min_score": Measure(_score(func.min), "score", "Lowest numeric score"),
            "max_score": Measure(_score(func.max), "score", "Highest numeric score"),
            "automated_passed": Measure(
                _count_where(ME.automated_success.is_(True)),
                "count",
                "Evaluations the metric itself passed, before human overrides",
            ),
            "automated_failed": Measure(
                _count_where(ME.automated_success.is_(False)),
                "count",
                "Evaluations the metric itself failed, before human overrides",
            ),
            "human_annotation_count": Measure(
                _count_where(ME.has_override.is_(True)),
                "count",
                "Evaluations a person overrode",
            ),
        },
        filters={
            "metric_names": Filter(ME.metric_name, "Metric names"),
            "requirement_ids": Filter(ME.requirement_id, "Requirement IDs"),
            "category_ids": Filter(ME.category_id, "Category IDs"),
            "topic_ids": Filter(ME.topic_id, "Topic IDs"),
            "test_run_ids": Filter(ME.test_run_id, "Test run IDs"),
            "test_set_ids": Filter(ME.test_set_id, "Test set IDs (the set the run executed)"),
            "endpoint_ids": Filter(ME.endpoint_id, "Endpoint IDs"),
            "test_ids": Filter(ME.test_id, "Test IDs"),
        },
    ),
    "test_run": Entity(
        view=RN,
        description=(
            "One row per run. Use for run volume, completion and duration: runs per week, per "
            "test set, per endpoint, per executor, and how long they take. For pass rates of "
            "what a run tested, use test_result grouped by test_run."
        ),
        date_column=RN.created_at,
        id_column=RN.test_run_id,
        dimensions={
            "test_set": Dimension(RN.test_set_name, "Test set the run executed", RN.test_set_id),
            "endpoint": Dimension(RN.endpoint_name, "Endpoint the run targeted", RN.endpoint_id),
            "executor": Dimension(RN.executor_name, "User who started the run", RN.user_id),
            "status": Dimension(RN.status_name, "Run status", RN.status_id),
        },
        measures={
            "count": Measure(_count, "count", "Number of runs"),
            "completed": Measure(
                _count_where(RN.result == OverallTestResult.PASSED), "count", "Runs that finished"
            ),
            "failed": Measure(
                _count_where(RN.result == OverallTestResult.FAILED),
                "count",
                "Runs that aborted or errored",
            ),
            "completion_rate": Measure(
                _rate(
                    _count_where(RN.result == OverallTestResult.PASSED),
                    _count_where(RN.result == OverallTestResult.FAILED),
                ),
                "rate",
                "completed / (completed + failed) x 100",
            ),
            # Runs without timing (never started, still running) are left out.
            "avg_duration_ms": Measure(_run_duration(func.avg), "duration", "Mean run duration"),
            "p50_duration_ms": Measure(
                _run_duration_percentile(0.5), "duration", "Median run duration"
            ),
            "p95_duration_ms": Measure(
                _run_duration_percentile(0.95), "duration", "95th percentile run duration"
            ),
            "max_duration_ms": Measure(_run_duration(func.max), "duration", "Longest run"),
        },
        filters={
            "test_run_ids": Filter(RN.test_run_id, "Test run IDs"),
            "test_set_ids": Filter(RN.test_set_id, "Test set IDs"),
            "endpoint_ids": Filter(RN.endpoint_id, "Endpoint IDs"),
            "executor_ids": Filter(RN.user_id, "IDs of users who started the run"),
            "status_ids": Filter(RN.status_id, "Run status IDs"),
        },
    ),
    "test": Entity(
        # One row per test (not per result), so counts include tests that never ran --
        # test_result and metric are structurally blind to a test until it has a result.
        view=TS,
        description=(
            "One row per test, including tests that never ran. Use for test inventory: "
            "coverage per requirement or topic, and tests that have never run."
        ),
        date_column=TS.created_at,
        id_column=TS.test_id,
        dimensions={
            "requirement": Dimension(
                TS.requirement_name, "Requirement the test covers", TS.requirement_id
            ),
            "category": Dimension(TS.category_name, "Test category", TS.category_id),
            "topic": Dimension(TS.topic_name, "Test topic", TS.topic_id),
            "priority": Dimension(TS.priority, "Test priority"),
            "is_unrun": Dimension(TS.is_unrun, "True for tests with no results yet"),
        },
        measures={
            "count": Measure(_count, "count", "Number of tests"),
            "unrun_count": Measure(
                _count_where(TS.is_unrun.is_(True)), "count", "Tests with no results yet"
            ),
            "run_count": Measure(_sum(TS.run_count), "count", "Results across these tests"),
            "passed": Measure(_sum(TS.passed_count), "count", "Results that passed"),
            "failed": Measure(_sum(TS.failed_count), "count", "Results that failed"),
            "error_count": Measure(
                _sum(TS.error_count), "count", "Results whose execution errored"
            ),
            "pass_rate": Measure(
                _rate(_sum(TS.passed_count), _sum(TS.failed_count)),
                "rate",
                "passed / (passed + failed) x 100 across these tests' results",
            ),
        },
        filters={
            "requirement_ids": Filter(TS.requirement_id, "Requirement IDs"),
            "category_ids": Filter(TS.category_id, "Category IDs"),
            "topic_ids": Filter(TS.topic_id, "Topic IDs"),
            "status_ids": Filter(TS.test_status_id, "Test status IDs"),
            "test_ids": Filter(TS.test_id, "Test IDs"),
            "test_type_ids": Filter(TS.test_type_id, "Test type IDs"),
            "user_ids": Filter(TS.test_user_id, "IDs of users who created the test"),
            "assignee_ids": Filter(TS.assignee_id, "Test assignee user IDs"),
            "owner_ids": Filter(TS.owner_id, "Test owner user IDs"),
            "prompt_ids": Filter(TS.prompt_id, "Prompt IDs"),
            "test_set_ids": Filter(
                TS.test_id,
                "Test set IDs (tests that belong to the set)",
                subquery=_test_set_ids_subquery,
            ),
            "tags": Filter(TS.test_id, "Test tag names", subquery=_tags_subquery),
        },
    ),
    "trace": Entity(
        view=None,
        source=trace_stats,
        description=(
            "One row per trace (an LLM application request). Use for latency, token and cost "
            "questions: p95 latency per endpoint, cost per day, error rate by operation. Only "
            "test-run traces have a test_run and endpoint."
        ),
        date_column="start_time",
        dimensions={
            "environment": Dimension("environment", "Environment the trace was sent from"),
            "operation": Dimension("operation", "Name of the trace's root span"),
            "test_run": Dimension("test_run_name", "Test run that produced it", "test_run_id"),
            "endpoint": Dimension("endpoint_name", "Endpoint the test run targeted", "endpoint_id"),
            "has_error": Dimension("has_error", "True when any span in the trace errored"),
        },
        measures={
            "count": Measure(lambda c: func.count(), "count", "Number of traces"),
            "error_count": Measure(
                lambda c: cast(func.sum(c.error_flag), Integer),
                "count",
                "Traces with an errored span",
            ),
            "error_rate": Measure(_trace_rate, "rate", "Errored traces / all traces x 100"),
            "avg_duration_ms": Measure(
                _trace_round(func.avg, "duration_ms", 2), "duration", "Mean root-span duration"
            ),
            "p50_duration_ms": Measure(_trace_percentile(0.5), "duration", "Median duration"),
            "p95_duration_ms": Measure(
                _trace_percentile(0.95), "duration", "95th percentile duration"
            ),
            "p99_duration_ms": Measure(
                _trace_percentile(0.99), "duration", "99th percentile duration"
            ),
            "tokens": Measure(
                lambda c: cast(func.sum(c.tokens), Integer), "count", "Tokens across LLM calls"
            ),
            "input_tokens": Measure(
                lambda c: cast(func.sum(c.input_tokens), Integer), "count", "Input tokens"
            ),
            "output_tokens": Measure(
                lambda c: cast(func.sum(c.output_tokens), Integer), "count", "Output tokens"
            ),
            "cost_usd": Measure(
                _trace_round(func.sum, "cost_usd", 6), "currency", "Total LLM cost in USD"
            ),
            "avg_cost_usd": Measure(
                _trace_round(func.avg, "cost_usd", 6), "currency", "Mean LLM cost per trace in USD"
            ),
        },
        filters={
            "test_run_ids": Filter("test_run_id", "Test run IDs"),
            "endpoint_ids": Filter("endpoint_id", "Endpoint IDs (test-run traces only)"),
            "environments": Filter("environment", "Environment names"),
        },
    ),
}


_PERIOD_DESCRIPTION = "Start date of the time bucket (UTC); size set by time_grain"


def describe() -> Dict[str, Any]:
    """The registry as plain data, for GET /insights/schema."""
    return {
        "time_grains": list(TIME_GRAINS),
        "entities": {
            name: {
                "description": entity.description,
                "dimensions": {
                    PERIOD: {"description": _PERIOD_DESCRIPTION, "has_id": False},
                    **{
                        dim: {"description": d.description, "has_id": d.id is not None}
                        for dim, d in entity.dimensions.items()
                    },
                },
                "measures": {
                    m: {"description": measure.description, "kind": measure.kind}
                    for m, measure in entity.measures.items()
                },
                "filters": {f: flt.description for f, flt in entity.filters.items()},
            }
            for name, entity in REGISTRY.items()
        },
    }
