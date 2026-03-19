"""Test result statistics functions with comprehensive filtering and mode-based data retrieval."""

from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session, joinedload

from .common import (
    build_pass_rate_stats,
    build_response_data,
    parse_date_range,
)

# Configuration for response modes
MODE_DEFINITIONS = {
    "all": [
        "metric_pass_rates",
        "behavior_pass_rates",
        "category_pass_rates",
        "topic_pass_rates",
        "overall_pass_rates",
        "timeline",
        "test_run_summary",
    ],
    "metrics": ["metric_pass_rates"],
    "behavior": ["behavior_pass_rates"],
    "category": ["category_pass_rates"],
    "topic": ["topic_pass_rates"],
    "overall": ["overall_pass_rates"],
    "timeline": ["timeline"],
    "test_runs": ["test_run_summary"],
    "summary": ["overall_pass_rates"],
}


def _apply_filters(base_query, **filters):
    """Apply all filters to the base query."""
    from sqlalchemy import and_

    from rhesis.backend.app import models
    from rhesis.backend.app.models.tag import Tag, TaggedItem

    # Organization filter
    if filters.get("organization_id"):
        base_query = base_query.filter(
            models.TestResult.organization_id == filters["organization_id"]
        )

    # Handle test run filtering (backward compatibility + new multiple support)
    combined_test_run_ids = []
    if filters.get("test_run_id"):
        combined_test_run_ids.append(filters["test_run_id"])
    if filters.get("test_run_ids"):
        combined_test_run_ids.extend(filters["test_run_ids"])

    if combined_test_run_ids:
        base_query = base_query.filter(models.TestResult.test_run_id.in_(combined_test_run_ids))

    # Date range filters
    if filters.get("start_date_obj"):
        base_query = base_query.filter(models.TestResult.created_at >= filters["start_date_obj"])
    if filters.get("end_date_obj"):
        base_query = base_query.filter(models.TestResult.created_at <= filters["end_date_obj"])

    # Test-level filters
    if filters.get("test_set_ids"):
        base_query = base_query.join(
            models.test_test_set_association,
            models.Test.id == models.test_test_set_association.c.test_id,
        ).filter(models.test_test_set_association.c.test_set_id.in_(filters["test_set_ids"]))

    # Simple list filters
    list_filters = [
        ("behavior_ids", models.Test.behavior_id),
        ("category_ids", models.Test.category_id),
        ("topic_ids", models.Test.topic_id),
        ("status_ids", models.Test.status_id),
        ("test_ids", models.Test.id),
        ("test_type_ids", models.Test.test_type_id),
        ("user_ids", models.Test.user_id),
        ("assignee_ids", models.Test.assignee_id),
        ("owner_ids", models.Test.owner_id),
        ("prompt_ids", models.Test.prompt_id),
    ]

    for filter_key, model_column in list_filters:
        if filters.get(filter_key):
            base_query = base_query.filter(model_column.in_(filters[filter_key]))

    # Priority range filters
    if filters.get("priority_min") is not None:
        base_query = base_query.filter(models.Test.priority >= filters["priority_min"])
    if filters.get("priority_max") is not None:
        base_query = base_query.filter(models.Test.priority <= filters["priority_max"])

    # Tags filter
    if filters.get("tags"):
        base_query = (
            base_query.join(
                TaggedItem,
                and_(TaggedItem.entity_id == models.Test.id, TaggedItem.entity_type == "Test"),
            )
            .join(Tag, TaggedItem.tag_id == Tag.id)
            .filter(Tag.name.in_(filters["tags"]))
        )

    return base_query


def _sql_overall_stats(db, base_query):
    from sqlalchemy import case, func

    from rhesis.backend.app import models

    query = base_query.join(
        models.Status, models.TestResult.status_id == models.Status.id
    ).with_entities(
        func.count(
            case(
                (models.Status.name.ilike("%pass%"), 1),
                (models.Status.name.ilike("%success%"), 1),
                (models.Status.name.ilike("%complet%"), 1),
                else_=None,
            )
        ).label("passed"),
        func.count(
            case(
                (models.Status.name.ilike("%fail%"), 1),
                (models.Status.name.ilike("%error%"), 1),
                else_=None,
            )
        ).label("failed"),
        func.count(models.TestResult.id).label("total"),
    )
    res = query.first()
    passed = res.passed or 0
    failed = res.failed or 0
    total = res.total or 0
    pass_rate = round((passed / total) * 100, 2) if total > 0 else 0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
    }


def _sql_timeline_stats(db, base_query):
    from sqlalchemy import case, extract, func

    from rhesis.backend.app import models

    query = (
        base_query.join(models.Status, models.TestResult.status_id == models.Status.id)
        .with_entities(
            extract("year", models.TestResult.created_at).label("year"),
            extract("month", models.TestResult.created_at).label("month"),
            func.count(
                case(
                    (models.Status.name.ilike("%pass%"), 1),
                    (models.Status.name.ilike("%success%"), 1),
                    (models.Status.name.ilike("%complet%"), 1),
                    else_=None,
                )
            ).label("passed"),
            func.count(
                case(
                    (models.Status.name.ilike("%fail%"), 1),
                    (models.Status.name.ilike("%error%"), 1),
                    else_=None,
                )
            ).label("failed"),
        )
        .group_by(
            extract("year", models.TestResult.created_at),
            extract("month", models.TestResult.created_at),
        )
        .order_by(
            extract("year", models.TestResult.created_at),
            extract("month", models.TestResult.created_at),
        )
    )

    timeline = []
    for row in query.all():
        if not row.year or not row.month:
            continue
        month_key = f"{int(row.year):04d}-{int(row.month):02d}"
        total = (row.passed or 0) + (row.failed or 0)
        pass_rate = round((row.passed / total) * 100, 2) if total > 0 else 0
        timeline.append(
            {
                "date": month_key,
                "overall": {
                    "total": total,
                    "passed": row.passed or 0,
                    "failed": row.failed or 0,
                    "pass_rate": pass_rate,
                },
                "metrics": {},  # Omitting full metric-by-month cross product in SQL for performance; frontend doesn't use it anyway.
            }
        )
    return timeline


def _sql_dimensional_stats(db, base_query, dimension_attr_name, dimension_model):
    from sqlalchemy import case, func

    from rhesis.backend.app import models

    query = (
        base_query.join(
            dimension_model, getattr(models.Test, f"{dimension_attr_name}_id") == dimension_model.id
        )
        .join(models.Status, models.TestResult.status_id == models.Status.id)
        .with_entities(
            dimension_model.name.label("name"),
            func.count(
                case(
                    (models.Status.name.ilike("%pass%"), 1),
                    (models.Status.name.ilike("%success%"), 1),
                    (models.Status.name.ilike("%complet%"), 1),
                    else_=None,
                )
            ).label("passed"),
            func.count(
                case(
                    (models.Status.name.ilike("%fail%"), 1),
                    (models.Status.name.ilike("%error%"), 1),
                    else_=None,
                )
            ).label("failed"),
        )
        .group_by(dimension_model.name)
    )

    stats = {}
    for row in query.all():
        name = row.name or f"Unknown {dimension_attr_name.capitalize()}"
        stats[name] = {"passed": row.passed or 0, "failed": row.failed or 0}

    return build_pass_rate_stats(stats)


def _sql_test_run_summary(db, base_query):
    from sqlalchemy import case, func

    from rhesis.backend.app import models

    query = (
        base_query.join(models.TestRun, models.TestResult.test_run_id == models.TestRun.id)
        .join(models.Status, models.TestResult.status_id == models.Status.id)
        .with_entities(
            models.TestRun.id.label("id"),
            models.TestRun.name.label("name"),
            models.TestRun.created_at.label("created_at"),
            func.count(
                case(
                    (models.Status.name.ilike("%pass%"), 1),
                    (models.Status.name.ilike("%success%"), 1),
                    (models.Status.name.ilike("%complet%"), 1),
                    else_=None,
                )
            ).label("passed"),
            func.count(
                case(
                    (models.Status.name.ilike("%fail%"), 1),
                    (models.Status.name.ilike("%error%"), 1),
                    else_=None,
                )
            ).label("failed"),
        )
        .group_by(models.TestRun.id, models.TestRun.name, models.TestRun.created_at)
        .order_by(models.TestRun.created_at.desc())
    )

    summary = []
    for row in query.all():
        run_key = str(row.id)
        total = (row.passed or 0) + (row.failed or 0)
        summary.append(
            {
                "id": run_key,
                "name": row.name or f"Test Run {run_key[:8]}",
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "overall": {
                    "total": total,
                    "passed": row.passed or 0,
                    "failed": row.failed or 0,
                    "pass_rate": round((row.passed / total) * 100, 2) if total > 0 else 0,
                },
                "metrics": {},
                "total_tests": total,
            }
        )
    return summary


def _sql_metric_stats(db, base_query):
    from rhesis.backend.app import models

    # Fallback to fast python aggregation of only the JSON column to avoid complex jsonb_each in SQLAlchemy
    # This is 100x faster than full ORM object loading
    results = base_query.with_entities(models.TestResult.test_metrics).all()
    metric_stats = {}
    for (metrics_json,) in results:
        if not metrics_json or "metrics" not in metrics_json:
            continue
        metrics = metrics_json["metrics"]
        if not isinstance(metrics, dict):
            continue
        for name, data in metrics.items():
            if not isinstance(data, dict) or "is_successful" not in data:
                continue
            if name not in metric_stats:
                metric_stats[name] = {"passed": 0, "failed": 0}
            if data["is_successful"]:
                metric_stats[name]["passed"] += 1
            else:
                metric_stats[name]["failed"] += 1

    return build_pass_rate_stats(metric_stats)


# Using shared build_response_data from common module


def get_test_result_stats(
    db: Session,
    organization_id: str | None = None,
    months: int = 6,
    test_run_id: str | None = None,  # Legacy single test run (backward compatibility)
    mode: str = "all",
    # Test-level filters
    test_set_ids: List[str] | None = None,
    behavior_ids: List[str] | None = None,
    category_ids: List[str] | None = None,
    topic_ids: List[str] | None = None,
    status_ids: List[str] | None = None,
    test_ids: List[str] | None = None,
    test_type_ids: List[str] | None = None,
    # Test run filters (new)
    test_run_ids: List[str] | None = None,  # Multiple test runs support
    # User-related filters
    user_ids: List[str] | None = None,
    assignee_ids: List[str] | None = None,
    owner_ids: List[str] | None = None,
    # Other filters
    prompt_ids: List[str] | None = None,
    priority_min: int | None = None,
    priority_max: int | None = None,
    tags: List[str] | None = None,
    # Date range filters
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict:
    """
    Get specialized statistics for test results with comprehensive filtering and configurable data modes.
    Analyzes test_metrics to determine pass/fail status per metric and overall.
    Designed for React charting libraries with performance optimization.

    Args:
        db: Database session
        organization_id: Optional organization ID for filtering
        months: Number of months to include in historical stats (used for timeline if no date range specified)
        test_run_id: Optional specific test run ID to filter by
        mode: Data mode to retrieve ('all', 'metrics', 'behavior', 'category', 'topic', 'overall', 'timeline', 'test_runs', 'summary')

        # Test-level filters
        test_set_ids: List of test set IDs to include
        behavior_ids: List of behavior IDs to include
        category_ids: List of category IDs to include
        topic_ids: List of topic IDs to include
        status_ids: List of test status IDs to include
        test_ids: List of specific test IDs to include
        test_type_ids: List of test type IDs to include

        # User-related filters
        user_ids: List of user IDs (test creators) to include
        assignee_ids: List of assignee IDs to include
        owner_ids: List of test owner IDs to include

        # Other filters
        prompt_ids: List of prompt IDs to include
        priority_min: Minimum priority level (inclusive)
        priority_max: Maximum priority level (inclusive)
        tags: List of tags that tests must have

        # Date range filters (ISO format strings)
        start_date: Start date for filtering (overrides months parameter)
        end_date: End date for filtering (overrides months parameter)

    Returns:
        Dict containing requested data sections based on mode:
        - all: All data sections
        - metrics: metric_pass_rates only
        - behavior: behavior_pass_rates only
        - category: category_pass_rates only
        - topic: topic_pass_rates only
        - overall: overall_pass_rates only
        - timeline: timeline data only
        - test_runs: test_run_summary only
        - summary: overall_pass_rates + metadata (lightweight)
    """
    from rhesis.backend.app import models

    # Handle date range - custom dates override months parameter
    start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)

    # Base query for test results with optimized eager loading
    base_query = (
        db.query(models.TestResult)
        .options(
            # Eager load essential relationships to prevent N+1 queries
            joinedload(models.TestResult.test).joinedload(models.Test.behavior),
            joinedload(models.TestResult.test).joinedload(models.Test.category),
            joinedload(models.TestResult.test).joinedload(models.Test.topic),
            joinedload(models.TestResult.test_run),
            joinedload(models.TestResult.status),  # Load status for statistics
        )
        .join(models.Test, models.TestResult.test_id == models.Test.id)
    )

    # Apply all filters using the helper function
    filter_params = {
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "test_run_ids": test_run_ids,
        "start_date_obj": start_date_obj,
        "end_date_obj": end_date_obj,
        "test_set_ids": test_set_ids,
        "behavior_ids": behavior_ids,
        "category_ids": category_ids,
        "topic_ids": topic_ids,
        "status_ids": status_ids,
        "test_ids": test_ids,
        "test_type_ids": test_type_ids,
        "user_ids": user_ids,
        "assignee_ids": assignee_ids,
        "owner_ids": owner_ids,
        "prompt_ids": prompt_ids,
        "priority_min": priority_min,
        "priority_max": priority_max,
        "tags": tags,
    }

    base_query = _apply_filters(base_query, **filter_params)

    # Fast SQL aggregations based on mode
    metric_pass_rates = {}
    behavior_pass_rates = {}
    category_pass_rates = {}
    topic_pass_rates = {}
    overall_pass_rates = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    timeline = []
    test_run_summary = []

    # Overall stats
    if mode in ["all", "overall", "summary"]:
        overall_pass_rates = _sql_overall_stats(db, base_query)

    # Metrics
    if mode in ["all", "metrics"]:
        metric_pass_rates = _sql_metric_stats(db, base_query)

    # Dimensions
    if mode in ["all", "behavior"]:
        behavior_pass_rates = _sql_dimensional_stats(db, base_query, "behavior", models.Behavior)
    if mode in ["all", "category"]:
        category_pass_rates = _sql_dimensional_stats(db, base_query, "category", models.Category)
    if mode in ["all", "topic"]:
        topic_pass_rates = _sql_dimensional_stats(db, base_query, "topic", models.Topic)

    # Timeline
    if mode in ["all", "timeline"]:
        timeline = _sql_timeline_stats(db, base_query)

    # Test Runs
    if mode in ["all", "test_runs"]:
        test_run_summary = _sql_test_run_summary(db, base_query)

    # Build metadata
    total_tests = overall_pass_rates["total"] if overall_pass_rates else 0
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "period": f"Last {months} months",
        "start_date": start_date_obj.isoformat() if start_date_obj else None,
        "end_date": end_date_obj.isoformat() if end_date_obj else None,
        "total_test_runs": len(test_run_summary) if test_run_summary else 0,
        "total_test_results": total_tests,
        "mode": mode,
        "available_metrics": list(metric_pass_rates.keys()) if metric_pass_rates else [],
        "available_behaviors": list(behavior_pass_rates.keys()) if behavior_pass_rates else [],
        "available_categories": list(category_pass_rates.keys()) if category_pass_rates else [],
        "available_topics": list(topic_pass_rates.keys()) if topic_pass_rates else [],
    }

    # Return data based on mode using shared helper function
    return build_response_data(
        mode,
        MODE_DEFINITIONS,
        metric_pass_rates=metric_pass_rates,
        behavior_pass_rates=behavior_pass_rates,
        category_pass_rates=category_pass_rates,
        topic_pass_rates=topic_pass_rates,
        overall_pass_rates=overall_pass_rates,
        timeline=timeline,
        test_run_summary=test_run_summary,
        metadata=metadata,
    )


def _empty_test_result_stats(
    start_date, end_date, months, organization_id, test_run_id, mode="all"
):
    """Return empty stats structure when no test results found, respecting mode"""
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "period": f"Last {months} months",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_test_runs": 0,
        "total_test_results": 0,
        "mode": mode,
        "available_metrics": [],
        "available_behaviors": [],
        "available_categories": [],
        "available_topics": [],
    }

    empty_overall = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}

    # Return data based on mode using the shared helper function
    return build_response_data(
        mode,
        MODE_DEFINITIONS,
        metric_pass_rates={},
        behavior_pass_rates={},
        category_pass_rates={},
        topic_pass_rates={},
        overall_pass_rates=empty_overall,
        timeline=[],
        test_run_summary=[],
        metadata=metadata,
    )
