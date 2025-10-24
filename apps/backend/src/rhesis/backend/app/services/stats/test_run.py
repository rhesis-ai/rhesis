"""Test run statistics functions with comprehensive filtering and mode-based data retrieval."""

from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from .common import (
    apply_top_limit,
    build_empty_stats_response,
    build_metadata,
    build_response_data,
    get_month_key,
    infer_result_from_status,
    parse_date_range,
    safe_get_name,
    safe_get_user_display_name,
    update_monthly_stats,
)

# Configuration for response modes
MODE_DEFINITIONS = {
    "all": [
        "status_distribution",
        "result_distribution",
        "most_run_test_sets",
        "top_executors",
        "timeline",
        "overall_summary",
    ],
    "status": ["status_distribution"],
    "results": ["result_distribution"],
    "test_sets": ["most_run_test_sets"],
    "executors": ["top_executors"],
    "timeline": ["timeline"],
    "summary": ["overall_summary"],
}


def _apply_filters(base_query, **filters):
    """Apply all filters to the base query."""

    from rhesis.backend.app import models

    # Organization filter
    if filters.get("organization_id"):
        base_query = base_query.filter(models.TestRun.organization_id == filters["organization_id"])

    # Date range filters
    if filters.get("start_date_obj"):
        base_query = base_query.filter(models.TestRun.created_at >= filters["start_date_obj"])
    if filters.get("end_date_obj"):
        base_query = base_query.filter(models.TestRun.created_at <= filters["end_date_obj"])

    # Test run specific filters
    if filters.get("test_run_ids"):
        base_query = base_query.filter(models.TestRun.id.in_(filters["test_run_ids"]))

    # User filters
    if filters.get("user_ids"):
        base_query = base_query.filter(models.TestRun.user_id.in_(filters["user_ids"]))

    # Test configuration filters
    if filters.get("endpoint_ids"):
        base_query = base_query.join(
            models.TestConfiguration,
            models.TestRun.test_configuration_id == models.TestConfiguration.id,
        ).filter(models.TestConfiguration.endpoint_id.in_(filters["endpoint_ids"]))

    if filters.get("test_set_ids"):
        base_query = base_query.join(
            models.TestConfiguration,
            models.TestRun.test_configuration_id == models.TestConfiguration.id,
        ).filter(models.TestConfiguration.test_set_id.in_(filters["test_set_ids"]))

    # Status filters
    if filters.get("status_list"):
        base_query = base_query.filter(models.TestRun.status.in_(filters["status_list"]))

    return base_query


def _compute_test_result_distribution(
    db: Session, test_run_ids: List[str], organization_id: str = None
) -> Dict[str, int]:
    """
    Compute the distribution of test results by analyzing their test_metrics.
    Uses the same approach as test_result stats to determine pass/fail based on metrics.
    """
    from rhesis.backend.app import models

    if not test_run_ids:
        return {"passed": 0, "failed": 0, "pending": 0}

    # Get all test results with their test_metrics (SECURITY: Include organization filtering)
    query = db.query(models.TestResult).filter(models.TestResult.test_run_id.in_(test_run_ids))

    # Apply organization filtering if provided (SECURITY CRITICAL)
    if organization_id:
        from uuid import UUID

        query = query.filter(models.TestResult.organization_id == UUID(organization_id))

    test_results = query.all()

    # Count results by analyzing metrics (same logic as test_result.py)
    passed = 0
    failed = 0
    pending = 0

    for result in test_results:
        if not result.test_metrics or "metrics" not in result.test_metrics:
            pending += 1
            continue

        metrics = result.test_metrics["metrics"]
        if not isinstance(metrics, dict):
            pending += 1
            continue

        # Determine if this test result passed overall
        test_passed_overall = True

        for metric_name, metric_data in metrics.items():
            if not isinstance(metric_data, dict) or "is_successful" not in metric_data:
                continue

            is_successful = metric_data["is_successful"]
            if not is_successful:
                test_passed_overall = False
                break

        # Count based on overall result
        if test_passed_overall:
            passed += 1
        else:
            failed += 1

    return {"passed": passed, "failed": failed, "pending": pending}


def _build_timeline_data(monthly_stats: Dict[str, Dict]) -> List[Dict[str, Any]]:
    """Build timeline data from monthly statistics."""
    timeline = []
    for month_key in sorted(monthly_stats.keys()):
        month_data = monthly_stats[month_key]
        timeline.append(
            {
                "date": month_key,
                "total_runs": month_data["total"],
                "status_breakdown": month_data["statuses"],
                "result_breakdown": month_data["results"],
            }
        )
    return timeline


def _get_optimized_aggregated_stats(
    db: Session, base_query, mode: str, top: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get aggregated statistics using SQL for better performance.
    Only fetches the data needed for the specific mode.
    """
    from sqlalchemy import case, extract

    from rhesis.backend.app import models

    stats = {}

    # Status distribution (needed for: all, status, summary)
    if mode in ["all", "status", "summary"]:
        status_query = (
            base_query.join(models.Status, models.TestRun.status_id == models.Status.id)
            .with_entities(
                models.Status.name.label("status_name"),
                func.count(models.TestRun.id).label("count"),
            )
            .group_by(models.Status.name)
        )

        if top:
            status_query = status_query.order_by(desc("count")).limit(top)

        status_results = status_query.all()
        stats["status_distribution"] = [
            {"status": row.status_name, "count": row.count} for row in status_results
        ]

    # Test sets (needed for: all, test_sets)
    if mode in ["all", "test_sets"]:
        test_sets_query = (
            base_query.join(
                models.TestConfiguration,
                models.TestRun.test_configuration_id == models.TestConfiguration.id,
            )
            .join(models.TestSet, models.TestConfiguration.test_set_id == models.TestSet.id)
            .with_entities(
                models.TestSet.name.label("test_set_name"),
                func.count(models.TestRun.id).label("run_count"),
            )
            .group_by(models.TestSet.name)
            .order_by(desc("run_count"))
        )

        if top:
            test_sets_query = test_sets_query.limit(top)

        test_sets_results = test_sets_query.all()
        stats["most_run_test_sets"] = [
            {"test_set_name": row.test_set_name, "run_count": row.run_count}
            for row in test_sets_results
        ]

    # Executors (needed for: all, executors)
    if mode in ["all", "executors"]:
        executors_query = (
            base_query.join(models.User, models.TestRun.user_id == models.User.id)
            .with_entities(
                func.coalesce(models.User.email, models.User.name, models.User.id).label(
                    "executor_name"
                ),
                func.count(models.TestRun.id).label("run_count"),
            )
            .group_by(func.coalesce(models.User.email, models.User.name, models.User.id))
            .order_by(desc("run_count"))
        )

        if top:
            executors_query = executors_query.limit(top)

        executors_results = executors_query.all()
        stats["top_executors"] = [
            {"executor_name": row.executor_name, "run_count": row.run_count}
            for row in executors_results
        ]

    # Result distribution (needed for: all, results, summary)
    if mode in ["all", "results", "summary"]:
        # This is more complex as we need to infer results from status
        # For now, let's use a simplified approach
        result_query = (
            base_query.join(
                models.Status, models.TestRun.status_id == models.Status.id
            ).with_entities(
                func.count(case((models.Status.name.ilike("%complet%"), 1), else_=None)).label(
                    "passed"
                ),
                func.count(case((models.Status.name.ilike("%fail%"), 1), else_=None)).label(
                    "failed"
                ),
                func.count(
                    case(
                        (
                            ~models.Status.name.ilike("%complet%")
                            & ~models.Status.name.ilike("%fail%"),
                            1,
                        ),
                        else_=None,
                    )
                ).label("pending"),
            )
        ).first()

        total_results = result_query.passed + result_query.failed + result_query.pending
        pass_rate = (
            round((result_query.passed / total_results) * 100, 2) if total_results > 0 else 0
        )

        stats["result_distribution"] = {
            "passed": result_query.passed,
            "failed": result_query.failed,
            "pending": result_query.pending,
            "pass_rate": pass_rate,
        }

    # Timeline data (needed for: all, timeline)
    if mode in ["all", "timeline"]:
        timeline_query = (
            base_query.join(models.Status, models.TestRun.status_id == models.Status.id)
            .with_entities(
                extract("year", models.TestRun.created_at).label("year"),
                extract("month", models.TestRun.created_at).label("month"),
                func.count(models.TestRun.id).label("total_runs"),
                func.count(case((models.Status.name.ilike("%complet%"), 1), else_=None)).label(
                    "passed"
                ),
                func.count(case((models.Status.name.ilike("%fail%"), 1), else_=None)).label(
                    "failed"
                ),
            )
            .group_by(
                extract("year", models.TestRun.created_at),
                extract("month", models.TestRun.created_at),
            )
            .order_by(
                extract("year", models.TestRun.created_at),
                extract("month", models.TestRun.created_at),
            )
        )

        timeline_results = timeline_query.all()
        timeline_data = []
        for row in timeline_results:
            month_key = f"{int(row.year):04d}-{int(row.month):02d}"
            pending = row.total_runs - row.passed - row.failed
            timeline_data.append(
                {
                    "month": month_key,
                    "total_runs": row.total_runs,
                    "passed": row.passed,
                    "failed": row.failed,
                    "pending": pending,
                    "pass_rate": round((row.passed / row.total_runs) * 100, 2)
                    if row.total_runs > 0
                    else 0,
                }
            )

        stats["timeline"] = timeline_data

    return stats


def get_test_run_stats(
    db: Session,
    organization_id: str | None = None,
    months: int = 6,
    mode: str = "all",
    top: int | None = None,
    # Test run filters
    test_run_ids: List[str] | None = None,
    # User-related filters
    user_ids: List[str] | None = None,
    # Configuration filters
    endpoint_ids: List[str] | None = None,
    test_set_ids: List[str] | None = None,
    # Status filters
    status_list: List[str] | None = None,
    # Date range filters
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict:
    """
    Get specialized statistics for test runs with comprehensive filtering and configurable data modes.
    Analyzes test run status, results, and execution patterns.
    Designed for React charting libraries with performance optimization.

    Args:
        db: Database session
        organization_id: Optional organization ID for filtering
        months: Number of months to include in historical stats (used for timeline if no date range specified)
        mode: Data mode to retrieve ('all', 'status', 'results', 'tests', 'executors', 'timeline', 'summary')
        top: Optional number of top items to show per dimension

        # Test run filters
        test_run_ids: List of test run IDs to include

        # User-related filters
        user_ids: List of user IDs (test run executors) to include

        # Configuration filters
        endpoint_ids: List of endpoint IDs to include
        test_set_ids: List of test set IDs to include

        # Status filters
        status_list: List of test run statuses to include

        # Date range filters (ISO format strings)
        start_date: Start date for filtering (overrides months parameter)
        end_date: End date for filtering (overrides months parameter)

    Returns:
        Dict containing requested data sections based on mode:
        - all: All data sections
        - status: status_distribution only
        - results: result_distribution only
        - test_sets: most_run_test_sets only
        - executors: top_executors only
        - timeline: timeline data only
        - summary: overall_summary + metadata (lightweight)
    """
    from rhesis.backend.app import models

    # Handle date range - custom dates override months parameter
    start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)

    # Base query for test runs with selective eager loading (excluding test results for performance)
    base_query = (
        db.query(models.TestRun)
        .options(
            # Eager load essential relationships but NOT test results (too many)
            joinedload(models.TestRun.status),
            joinedload(models.TestRun.user),
            joinedload(models.TestRun.test_configuration).joinedload(
                models.TestConfiguration.test_set
            ),
        )
        .join(
            models.TestConfiguration,
            models.TestRun.test_configuration_id == models.TestConfiguration.id,
        )
        .join(models.TestSet, models.TestConfiguration.test_set_id == models.TestSet.id)
    )

    # Apply all filters using the helper function
    filter_params = {
        "organization_id": organization_id,
        "test_run_ids": test_run_ids,
        "start_date_obj": start_date_obj,
        "end_date_obj": end_date_obj,
        "user_ids": user_ids,
        "endpoint_ids": endpoint_ids,
        "test_set_ids": test_set_ids,
        "status_list": status_list,
    }

    base_query = _apply_filters(base_query, **filter_params)

    # Add ordering for consistent results
    base_query = base_query.order_by(models.TestRun.created_at.desc())

    # Note: Removed LIMIT clause to ensure complete data accuracy
    # Performance is optimized through eager loading and efficient queries

    # Get all test runs with eager loading to prevent N+1 queries
    test_runs = base_query.all()

    if not test_runs:
        return build_empty_stats_response(
            mode=mode,
            mode_definitions=MODE_DEFINITIONS,
            start_date_obj=start_date_obj,
            end_date_obj=end_date_obj,
            months=months,
            organization_id=organization_id,
            total_test_runs=0,
            available_statuses=[],
            available_test_sets=[],
            available_executors=[],
        )

    # Efficiently compute test result distribution using SQL aggregation
    test_run_ids = [str(test_run.id) for test_run in test_runs]
    result_stats = _compute_test_result_distribution(db, test_run_ids, organization_id)

    # Initialize other statistics containers
    status_stats = {}  # status -> count
    test_stats = {}  # test_set_name -> count
    executor_stats = {}  # user_name -> count
    monthly_stats = {}  # "YYYY-MM" -> {total, statuses: {}, results: {}}

    for test_run in test_runs:
        # Status distribution - use the actual status name from the relationship
        status_name = safe_get_name(test_run.status)
        if status_name not in status_stats:
            status_stats[status_name] = 0
        status_stats[status_name] += 1

        # Note: Result distribution will be computed separately from all test results
        # This loop only handles test run-level statistics

        # Most run tests (by test set)
        if test_run.test_configuration and test_run.test_configuration.test_set:
            test_set_name = safe_get_name(test_run.test_configuration.test_set)
            if test_set_name not in test_stats:
                test_stats[test_set_name] = 0
            test_stats[test_set_name] += 1

        # Top executors
        executor_name = safe_get_user_display_name(test_run.user)
        if executor_name not in executor_stats:
            executor_stats[executor_name] = 0
        executor_stats[executor_name] += 1

        # Monthly timeline data (for test run counts, not test result counts)
        if test_run.created_at:
            month_key = get_month_key(test_run.created_at)
            # For timeline, we track test run status, not test result status
            # Test result distribution is computed separately above
            result = infer_result_from_status(status_name)
            update_monthly_stats(monthly_stats, month_key, status_name, result)

    # Apply top limit if specified
    if top:
        test_stats = apply_top_limit(test_stats, top)
        executor_stats = apply_top_limit(executor_stats, top)

    # Build status distribution
    status_distribution = [
        {"status": status, "count": count, "percentage": round((count / len(test_runs)) * 100, 2)}
        for status, count in status_stats.items()
    ]

    # Build result distribution
    total_results = sum(result_stats.values())
    result_distribution = {
        "total": total_results,
        "passed": result_stats["passed"],
        "failed": result_stats["failed"],
        "pending": result_stats["pending"],
        "pass_rate": round((result_stats["passed"] / total_results) * 100, 2)
        if total_results > 0
        else 0,
    }

    # Build most run test sets
    most_run_test_sets = [
        {"test_set_name": name, "run_count": count}
        for name, count in sorted(test_stats.items(), key=lambda x: x[1], reverse=True)
    ]

    # Build top executors
    top_executors = [
        {"executor_name": name, "run_count": count}
        for name, count in sorted(executor_stats.items(), key=lambda x: x[1], reverse=True)
    ]

    # Build timeline data using helper function
    timeline = _build_timeline_data(monthly_stats)

    # Build overall summary
    overall_summary = {
        "total_runs": len(test_runs),
        "unique_test_sets": len(test_stats),
        "unique_executors": len(executor_stats),
        "most_common_status": max(status_stats.items(), key=lambda x: x[1])[0]
        if status_stats
        else "unknown",
        "pass_rate": result_distribution["pass_rate"],
    }

    # Build metadata
    metadata = build_metadata(
        organization_id=organization_id,
        start_date_obj=start_date_obj,
        end_date_obj=end_date_obj,
        months=months,
        mode=mode,
        total_items=len(test_runs),
        total_test_runs=len(test_runs),
        available_statuses=list(status_stats.keys()),
        available_test_sets=list(test_stats.keys()),
        available_executors=list(executor_stats.keys()),
    )

    # Return data based on mode using shared helper function
    return build_response_data(
        mode,
        MODE_DEFINITIONS,
        status_distribution=status_distribution,
        result_distribution=result_distribution,
        most_run_test_sets=most_run_test_sets,
        top_executors=top_executors,
        timeline=timeline,
        overall_summary=overall_summary,
        metadata=metadata,
    )
