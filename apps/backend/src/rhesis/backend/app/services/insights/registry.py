"""Declarative registry of what Insights endpoints can query.

Each entity names the view backing it, the columns valid as group_by
dimensions, the measures computable over it, and the filters accepted.
query_builder.py validates every incoming param against this before
touching the database.

Optional keys used only by GET /insights/ids:
  id_column     — column to SELECT DISTINCT
  apply_outcome — (view, 'pass'|'fail') -> SQL expression
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


def _passed(condition):
    return lambda: func.count().filter(condition)


def _failed(condition):
    return lambda: func.count().filter(condition)


def _pass_rate(passed_condition, failed_condition):
    """passed / (passed + failed) * 100 -- pending/inconclusive rows excluded from
    the denominator, matching build_pass_rate_stats()/_overall_stats() elsewhere."""

    def _measure():
        passed = func.count().filter(passed_condition)
        failed = func.count().filter(failed_condition)
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


def _overall_result_outcome(view, outcome: str):
    """Filter by overall test result ('pass' / 'fail')."""
    target = OverallTestResult.PASSED if outcome == "pass" else OverallTestResult.FAILED
    return view.result == target


def _metric_success_outcome(view, outcome: str):
    """Filter by metric effective_success ('pass' / 'fail')."""
    return view.effective_success.is_(outcome == "pass")


REGISTRY = {
    "test_result": {
        "view": TR,
        "date_column": TR.created_at,
        # GET /insights/ids — which column to SELECT DISTINCT, plus optional
        # outcome / topic_name predicates that only that endpoint uses.
        "id_column": TR.test_id,
        "apply_outcome": _overall_result_outcome,
        "dimensions": {
            "behavior": TR.behavior_name,
            "behavior_id": TR.behavior_id,
            "category": TR.category_name,
            "category_id": TR.category_id,
            "topic": TR.topic_name,
            "topic_id": TR.topic_id,
            "test_run": TR.run_id,
            "status": TR.status_name,
            "year": TR.year,
            "month": TR.month,
        },
        "measures": {
            "count": _count,
            "passed": _passed(TR.result == OverallTestResult.PASSED),
            "failed": _failed(TR.result == OverallTestResult.FAILED),
            "pass_rate": _pass_rate(
                TR.result == OverallTestResult.PASSED, TR.result == OverallTestResult.FAILED
            ),
        },
        "filters": {
            "test_run_ids": TR.test_run_id,
            "behavior_ids": TR.behavior_id,
            "category_ids": TR.category_id,
            "topic_ids": TR.topic_id,
            "status_ids": TR.result_status_id,
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
        "id_column": ME.test_id,
        "apply_outcome": _metric_success_outcome,
        "dimensions": {
            "metric_name": ME.metric_name,
            "behavior_id": ME.behavior_id,
            "year": ME.year,
            "month": ME.month,
        },
        "measures": {
            "count": _count,
            "passed": _passed(ME.effective_success.is_(True)),
            "failed": _failed(ME.effective_success.is_(False)),
            "pass_rate": _pass_rate(
                ME.effective_success.is_(True), ME.effective_success.is_(False)
            ),
            "automated_passed": lambda: func.count().filter(ME.automated_success.is_(True)),
            "automated_failed": lambda: func.count().filter(ME.automated_success.is_(False)),
            "human_review_count": lambda: func.count().filter(ME.has_override.is_(True)),
        },
        "filters": {
            "test_run_ids": ME.test_run_id,
            "behavior_ids": ME.behavior_id,
            "test_ids": ME.test_id,
            "metric_names": ME.metric_name,
        },
        "subquery_filters": {},
    },
    "test_run": {
        "view": RN,
        "date_column": RN.created_at,
        "id_column": RN.test_run_id,
        "dimensions": {
            "status": RN.status_name,
            "test_set": RN.test_set_name,
            "executor": RN.executor_name,
            "year": RN.year,
            "month": RN.month,
        },
        "measures": {
            "count": _count,
            "passed": _passed(RN.result == OverallTestResult.PASSED),
            "failed": _failed(RN.result == OverallTestResult.FAILED),
            "pass_rate": _pass_rate(
                RN.result == OverallTestResult.PASSED, RN.result == OverallTestResult.FAILED
            ),
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
        "id_column": TS.test_id,
        "dimensions": {
            "behavior": TS.behavior_name,
            "behavior_id": TS.behavior_id,
            "category": TS.category_name,
            "category_id": TS.category_id,
            "topic": TS.topic_name,
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
