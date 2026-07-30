"""Declarative registry of what GET /insights can query.

Each entity names the view backing it, the columns valid as group_by
dimensions, the measures computable over it (all as SQL aggregate
expressions -- no Python-side aggregation), and the filters accepted.
query_builder.py validates every incoming param against this before
touching the database and turns a validated request into one GROUP BY
query.

test_run is not backed by a JSONB-metrics column so it has no "metric"
counterpart.
"""

from sqlalchemy import Float, case, cast, func

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.models.stats_views import (
    MetricStatsView,
    TestResultStatsView,
    TestRunStatsView,
    TestStatsView,
)
from rhesis.backend.app.models.tag import Tag, TaggedItem
from rhesis.backend.app.models.test import test_test_set_association

TR = TestResultStatsView
RN = TestRunStatsView
ME = MetricStatsView
TS = TestStatsView


def _count():
    return func.count()


def _passed(view):
    return lambda: func.count().filter(view.result == OverallTestResult.PASSED)


def _failed(view):
    return lambda: func.count().filter(view.result == OverallTestResult.FAILED)


def _pass_rate(view):
    """passed / (passed + failed) * 100 -- pending results excluded from the
    denominator, matching build_pass_rate_stats()/_overall_stats() elsewhere."""

    def _measure():
        passed = func.count().filter(view.result == OverallTestResult.PASSED)
        failed = func.count().filter(view.result == OverallTestResult.FAILED)
        rate = case((passed + failed == 0, 0), else_=passed * 100.0 / (passed + failed))
        return cast(func.round(rate, 2), Float)

    return _measure


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


REGISTRY = {
    "test_result": {
        "view": TR,
        "date_column": TR.created_at,
        "dimensions": {
            "behavior": TR.behavior_name,
            "category": TR.category_name,
            "topic": TR.topic_name,
            "test_run": TR.run_id,
            "status": TR.status_name,
            "year": TR.year,
            "month": TR.month,
        },
        "measures": {
            "count": _count,
            "passed": _passed(TR),
            "failed": _failed(TR),
            "pass_rate": _pass_rate(TR),
        },
        "filters": {
            "test_run_ids": TR.test_run_id,
            "behavior_ids": TR.behavior_id,
            "category_ids": TR.category_id,
            "topic_ids": TR.topic_id,
            "status_ids": TR.test_status_id,
            "test_ids": TR.test_id,
            "test_type_ids": TR.test_type_id,
            "user_ids": TR.test_user_id,
            "assignee_ids": TR.assignee_id,
            "owner_ids": TR.owner_id,
            "prompt_ids": TR.prompt_id,
        },
        # subquery filters narrow TR.test_id to the ids a subquery returns,
        # for relationships the view can't flatten into a plain column
        # (many-to-many test sets, polymorphic tags).
        "subquery_filters": {
            "test_set_ids": (TR.test_id, _test_set_ids_subquery),
            "tags": (TR.test_id, _tags_subquery),
        },
    },
    "metric": {
        "view": ME,
        "date_column": ME.created_at,
        "dimensions": {
            "metric_name": ME.metric_name,
            "behavior_id": ME.behavior_id,
            "category_id": ME.category_id,
            "topic_id": ME.topic_id,
            "year": ME.year,
            "month": ME.month,
        },
        "measures": {
            "count": _count,
            "passed": lambda: func.count().filter(ME.effective_success.is_(True)),
            "failed": lambda: func.count().filter(ME.effective_success.is_(False)),
            "pass_rate": lambda: cast(
                func.round(
                    func.count().filter(ME.effective_success.is_(True)) * 100.0 / func.count(), 2
                ),
                Float,
            ),
            "automated_passed": lambda: func.count().filter(ME.automated_success.is_(True)),
            "automated_failed": lambda: func.count().filter(ME.automated_success.is_(False)),
            "human_review_count": lambda: func.count().filter(ME.has_override.is_(True)),
        },
        "filters": {
            "test_run_ids": ME.test_run_id,
            "behavior_ids": ME.behavior_id,
            "category_ids": ME.category_id,
            "topic_ids": ME.topic_id,
            "test_ids": ME.test_id,
            "metric_names": ME.metric_name,
        },
        "subquery_filters": {},
    },
    "test_run": {
        "view": RN,
        "date_column": RN.created_at,
        "dimensions": {
            "status": RN.status_name,
            "test_set": RN.test_set_name,
            "executor": RN.executor_name,
            "year": RN.year,
            "month": RN.month,
        },
        "measures": {
            "count": _count,
            "passed": _passed(RN),
            "failed": _failed(RN),
            "pass_rate": _pass_rate(RN),
        },
        "filters": {
            "test_run_ids": RN.test_run_id,
            "user_ids": RN.user_id,
            "endpoint_ids": RN.endpoint_id,
            "test_set_ids": RN.test_set_id,
        },
        "subquery_filters": {},
    },
    "test": {
        # One row per test (not per test_result), so counts here include
        # tests that have never been run -- unlike test_result/metric, which
        # are structurally invisible to a test until it has a result.
        "view": TS,
        "date_column": TS.created_at,
        "dimensions": {
            "behavior_id": TS.behavior_id,
            "category_id": TS.category_id,
            "topic_id": TS.topic_id,
            "test_type_id": TS.test_type_id,
            "status": TS.test_status_id,
            "is_unrun": TS.is_unrun,
            "year": TS.year,
            "month": TS.month,
        },
        "measures": {
            "count": _count,
            "unrun_count": lambda: func.count().filter(TS.is_unrun.is_(True)),
            "run_count": lambda: func.sum(TS.run_count),
            "passed": lambda: func.sum(TS.passed_count),
            "failed": lambda: func.sum(TS.failed_count),
            "pass_rate": lambda: cast(
                func.round(
                    case(
                        (func.sum(TS.passed_count) + func.sum(TS.failed_count) == 0, 0),
                        else_=func.sum(TS.passed_count)
                        * 100.0
                        / (func.sum(TS.passed_count) + func.sum(TS.failed_count)),
                    ),
                    2,
                ),
                Float,
            ),
        },
        "filters": {
            "behavior_ids": TS.behavior_id,
            "category_ids": TS.category_id,
            "topic_ids": TS.topic_id,
            "status_ids": TS.test_status_id,
            "test_ids": TS.test_id,
            "test_type_ids": TS.test_type_id,
            "user_ids": TS.test_user_id,
            "assignee_ids": TS.assignee_id,
            "owner_ids": TS.owner_id,
            "prompt_ids": TS.prompt_id,
        },
        "subquery_filters": {
            "test_set_ids": (TS.test_id, _test_set_ids_subquery),
            "tags": (TS.test_id, _tags_subquery),
        },
    },
}
