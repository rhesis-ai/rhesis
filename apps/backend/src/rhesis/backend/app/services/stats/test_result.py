"""Test result statistics functions with comprehensive filtering and mode-based data retrieval."""

from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session, joinedload

from .common import (
    build_pass_rate_stats,
    build_response_data,
    get_month_key,
    parse_date_range,
    safe_get_name,
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


# Using shared build_pass_rate_stats from common module


def _update_dimensional_stats(
    result,
    test_passed_overall: bool,
    dimensional_stats: Dict[str, Dict[str, int]],
    dimension_name: str,
    dimension_attr: str,
):
    """Update dimensional breakdown stats (behavior, category, topic)."""
    if hasattr(result, "test") and result.test:
        dimension_obj = getattr(result.test, dimension_attr, None)
        if dimension_obj:
            name = safe_get_name(dimension_obj) or f"Unknown {dimension_name.capitalize()}"
            if name not in dimensional_stats:
                dimensional_stats[name] = {"passed": 0, "failed": 0}
            if test_passed_overall:
                dimensional_stats[name]["passed"] += 1
            else:
                dimensional_stats[name]["failed"] += 1


def _build_timeline_data(monthly_stats: Dict[str, Dict]) -> List[Dict[str, Any]]:
    """Build timeline data from monthly statistics."""
    timeline = []
    for month_key in sorted(monthly_stats.keys()):
        month_data = monthly_stats[month_key]
        overall_total = month_data["overall"]["passed"] + month_data["overall"]["failed"]
        overall_pass_rate = (
            round((month_data["overall"]["passed"] / overall_total) * 100, 2)
            if overall_total > 0
            else 0
        )

        # Build metric breakdown for this month using shared helper
        metric_breakdown = build_pass_rate_stats(month_data["metrics"])

        timeline.append(
            {
                "date": month_key,
                "overall": {
                    "total": overall_total,
                    "passed": month_data["overall"]["passed"],
                    "failed": month_data["overall"]["failed"],
                    "pass_rate": overall_pass_rate,
                },
                "metrics": metric_breakdown,
            }
        )
    return timeline


def _build_test_run_summary(test_run_stats: Dict[str, Dict]) -> List[Dict[str, Any]]:
    """Build test run summary from test run statistics."""
    test_run_summary = []
    for run_data in test_run_stats.values():
        # Calculate overall pass rate for this run
        run_total = run_data["overall"]["passed"] + run_data["overall"]["failed"]
        run_pass_rate = (
            round((run_data["overall"]["passed"] / run_total) * 100, 2) if run_total > 0 else 0
        )

        # Calculate metric pass rates for this run using shared helper
        run_metric_breakdown = build_pass_rate_stats(run_data["metrics"])

        test_run_summary.append(
            {
                "id": run_data["id"],
                "name": run_data["name"],
                "created_at": run_data["created_at"],
                "total_tests": run_data["total_tests"],
                "overall": {
                    "total": run_total,
                    "passed": run_data["overall"]["passed"],
                    "failed": run_data["overall"]["failed"],
                    "pass_rate": run_pass_rate,
                },
                "metrics": run_metric_breakdown,
            }
        )

    # Sort test runs by creation date (newest first)
    test_run_summary.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return test_run_summary


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

    # Add ordering for consistent results and better query optimization
    base_query = base_query.order_by(models.TestResult.created_at.desc())

    # Note: Removed LIMIT clause to ensure complete data accuracy
    # Performance is optimized through eager loading and efficient queries instead

    # Get all test results with optimized eager loading
    test_results = base_query.all()

    if not test_results:
        return _empty_test_result_stats(
            start_date_obj, end_date_obj, months, organization_id, test_run_id, mode
        )

    # Parse metrics from all test results
    metric_stats = {}  # metric_name -> {passed: count, failed: count}
    overall_stats = {"passed": 0, "failed": 0}
    monthly_stats = {}  # "YYYY-MM" -> {overall: {passed, failed}, metrics: {metric_name: {passed, failed}}}
    test_run_stats = {}  # test_run_id -> stats

    # Dimensional breakdowns
    behavior_stats = {}  # behavior_name -> {passed: count, failed: count}
    category_stats = {}  # category_name -> {passed: count, failed: count}
    topic_stats = {}  # topic_name -> {passed: count, failed: count}

    for result in test_results:
        if not result.test_metrics or "metrics" not in result.test_metrics:
            continue

        metrics = result.test_metrics["metrics"]
        if not isinstance(metrics, dict):
            continue

        # Use stored test status as source of truth for overall pass/fail
        from rhesis.backend.app.constants import (
            STATUS_CATEGORY_PASSED,
            categorize_test_result_status,
        )

        status_name = result.status.name if result.status else None
        status_category = categorize_test_result_status(status_name)
        test_passed_overall = status_category == STATUS_CATEGORY_PASSED

        # Still track individual metric results for per-metric statistics
        test_metric_results = {}

        for metric_name, metric_data in metrics.items():
            if not isinstance(metric_data, dict) or "is_successful" not in metric_data:
                continue

            is_successful = metric_data["is_successful"]

            # Initialize metric stats if not exists
            if metric_name not in metric_stats:
                metric_stats[metric_name] = {"passed": 0, "failed": 0}

            # Update per-metric stats (still based on individual metric outcomes)
            if is_successful:
                metric_stats[metric_name]["passed"] += 1
            else:
                metric_stats[metric_name]["failed"] += 1

            test_metric_results[metric_name] = is_successful

        # Update overall stats using stored status
        if test_passed_overall:
            overall_stats["passed"] += 1
        else:
            overall_stats["failed"] += 1

        # Update dimensional stats (behavior, category, topic)
        _update_dimensional_stats(
            result, test_passed_overall, behavior_stats, "behavior", "behavior"
        )
        _update_dimensional_stats(
            result, test_passed_overall, category_stats, "category", "category"
        )
        _update_dimensional_stats(result, test_passed_overall, topic_stats, "topic", "topic")

        # Update monthly stats
        if result.created_at:
            month_key = get_month_key(result.created_at)
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {"overall": {"passed": 0, "failed": 0}, "metrics": {}}

            # Update monthly overall stats
            if test_passed_overall:
                monthly_stats[month_key]["overall"]["passed"] += 1
            else:
                monthly_stats[month_key]["overall"]["failed"] += 1

            # Update monthly metric stats
            for metric_name, is_successful in test_metric_results.items():
                if metric_name not in monthly_stats[month_key]["metrics"]:
                    monthly_stats[month_key]["metrics"][metric_name] = {"passed": 0, "failed": 0}

                if is_successful:
                    monthly_stats[month_key]["metrics"][metric_name]["passed"] += 1
                else:
                    monthly_stats[month_key]["metrics"][metric_name]["failed"] += 1

        # Update test run stats (using eager loaded test_run relationship)
        if result.test_run_id:
            run_key = str(result.test_run_id)
            if run_key not in test_run_stats:
                # Use eager loaded test_run relationship instead of separate query
                test_run = result.test_run if hasattr(result, "test_run") else None
                test_run_stats[run_key] = {
                    "id": run_key,
                    "name": test_run.name
                    if test_run and test_run.name
                    else f"Test Run {run_key[:8]}",
                    "created_at": test_run.created_at.isoformat()
                    if test_run and test_run.created_at
                    else None,
                    "overall": {"passed": 0, "failed": 0},
                    "metrics": {},
                    "total_tests": 0,
                }

            test_run_stats[run_key]["total_tests"] += 1

            # Update test run overall stats
            if test_passed_overall:
                test_run_stats[run_key]["overall"]["passed"] += 1
            else:
                test_run_stats[run_key]["overall"]["failed"] += 1

            # Update test run metric stats
            for metric_name, is_successful in test_metric_results.items():
                if metric_name not in test_run_stats[run_key]["metrics"]:
                    test_run_stats[run_key]["metrics"][metric_name] = {"passed": 0, "failed": 0}

                if is_successful:
                    test_run_stats[run_key]["metrics"][metric_name]["passed"] += 1
                else:
                    test_run_stats[run_key]["metrics"][metric_name]["failed"] += 1

    # Build pass rates using shared helper function
    metric_pass_rates = build_pass_rate_stats(metric_stats)
    behavior_pass_rates = build_pass_rate_stats(behavior_stats)
    category_pass_rates = build_pass_rate_stats(category_stats)
    topic_pass_rates = build_pass_rate_stats(topic_stats)

    # Build overall pass rates
    total_tests = overall_stats["passed"] + overall_stats["failed"]
    overall_pass_rate = (
        round((overall_stats["passed"] / total_tests) * 100, 2) if total_tests > 0 else 0
    )
    overall_pass_rates = {
        "total": total_tests,
        "passed": overall_stats["passed"],
        "failed": overall_stats["failed"],
        "pass_rate": overall_pass_rate,
    }

    # Build timeline data using helper function
    timeline = _build_timeline_data(monthly_stats)

    # Build test run summary using helper function
    test_run_summary = _build_test_run_summary(test_run_stats)

    # Build metadata (using original approach for compatibility)
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "period": f"Last {months} months",
        "start_date": start_date_obj.isoformat(),
        "end_date": end_date_obj.isoformat(),
        "total_test_runs": len(test_run_stats),
        "total_test_results": total_tests,
        "mode": mode,
        "available_metrics": list(metric_stats.keys()),
        "available_behaviors": list(behavior_stats.keys()),
        "available_categories": list(category_stats.keys()),
        "available_topics": list(topic_stats.keys()),
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
