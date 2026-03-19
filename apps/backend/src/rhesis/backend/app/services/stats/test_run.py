"""Test run statistics functions with comprehensive filtering and mode-based data retrieval."""

from typing import Any, Dict, List, Optional

from sqlalchemy import Text, cast, desc, func
from sqlalchemy.orm import Session

from .common import (
    build_empty_stats_response,
    build_metadata,
    build_response_data,
    parse_date_range,
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
    joined_test_config = False
    if filters.get("endpoint_ids"):
        base_query = base_query.join(
            models.TestConfiguration,
            models.TestRun.test_configuration_id == models.TestConfiguration.id,
        ).filter(models.TestConfiguration.endpoint_id.in_(filters["endpoint_ids"]))
        joined_test_config = True

    if filters.get("test_set_ids"):
        if not joined_test_config:
            base_query = base_query.join(
                models.TestConfiguration,
                models.TestRun.test_configuration_id == models.TestConfiguration.id,
            )
        base_query = base_query.filter(
            models.TestConfiguration.test_set_id.in_(filters["test_set_ids"])
        )

    # Status filters
    if filters.get("status_list"):
        base_query = base_query.filter(models.TestRun.status.in_(filters["status_list"]))

    return base_query


def _get_optimized_aggregated_stats(
    db: Session, base_query, mode: str, top: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get aggregated statistics using SQL for better performance.
    Only fetches the data needed for the specific mode.
    """
    from sqlalchemy import case, cast, extract, Text

    from rhesis.backend.app import models

    # Materialise a subquery of filtered test_run IDs so that each
    # aggregation query can join independently without duplicate aliases.
    run_ids_sq = (
        base_query
        .with_entities(models.TestRun.id)
        .subquery("filtered_runs")
    )

    stats = {}

    # Status distribution (needed for: all, status, summary)
    if mode in ["all", "status", "summary"]:
        status_query = (
            db.query(
                models.Status.name.label("status_name"),
                func.count(models.TestRun.id).label("count"),
            )
            .select_from(models.TestRun)
            .join(run_ids_sq, models.TestRun.id == run_ids_sq.c.id)
            .join(models.Status, models.TestRun.status_id == models.Status.id)
            .group_by(models.Status.name)
        )

        if top:
            status_query = status_query.order_by(desc("count")).limit(top)

        status_results = status_query.all()
        stats["status_distribution"] = [
            {"status": row.status_name, "count": row.count}
            for row in status_results
        ]

    # Test sets (needed for: all, test_sets)
    if mode in ["all", "test_sets"]:
        test_sets_query = (
            db.query(
                models.TestSet.name.label("test_set_name"),
                func.count(models.TestRun.id).label("run_count"),
            )
            .select_from(models.TestRun)
            .join(run_ids_sq, models.TestRun.id == run_ids_sq.c.id)
            .join(
                models.TestConfiguration,
                models.TestRun.test_configuration_id == models.TestConfiguration.id,
            )
            .join(
                models.TestSet,
                models.TestConfiguration.test_set_id == models.TestSet.id,
            )
            .filter(models.TestSet.deleted_at.is_(None))
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
        executor_name_expr = func.coalesce(
            models.User.email, models.User.name, cast(models.User.id, Text)
        )

        executors_query = (
            db.query(
                executor_name_expr.label("executor_name"),
                func.count(models.TestRun.id).label("run_count"),
            )
            .select_from(models.TestRun)
            .join(run_ids_sq, models.TestRun.id == run_ids_sq.c.id)
            .join(models.User, models.TestRun.user_id == models.User.id)
            .group_by(
                models.User.email, models.User.name, cast(models.User.id, Text)
            )
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
        result_query = (
            db.query(
                func.count(
                    case((models.Status.name.ilike("%complet%"), 1), else_=None)
                ).label("passed"),
                func.count(
                    case((models.Status.name.ilike("%fail%"), 1), else_=None)
                ).label("failed"),
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
            .select_from(models.TestRun)
            .join(run_ids_sq, models.TestRun.id == run_ids_sq.c.id)
            .join(models.Status, models.TestRun.status_id == models.Status.id)
        ).first()

        total_results = (
            result_query.passed + result_query.failed + result_query.pending
        )
        pass_rate = (
            round((result_query.passed / total_results) * 100, 2)
            if total_results > 0
            else 0
        )

        stats["result_distribution"] = {
            "total": total_results,
            "passed": result_query.passed,
            "failed": result_query.failed,
            "pending": result_query.pending,
            "pass_rate": pass_rate,
        }

    # Timeline data (needed for: all, timeline)
    if mode in ["all", "timeline"]:
        timeline_query = (
            db.query(
                extract("year", models.TestRun.created_at).label("year"),
                extract("month", models.TestRun.created_at).label("month"),
                func.count(models.TestRun.id).label("total_runs"),
                func.count(
                    case(
                        (models.Status.name.ilike("%complet%"), 1), else_=None
                    )
                ).label("passed"),
                func.count(
                    case(
                        (models.Status.name.ilike("%fail%"), 1), else_=None
                    )
                ).label("failed"),
            )
            .select_from(models.TestRun)
            .join(run_ids_sq, models.TestRun.id == run_ids_sq.c.id)
            .join(models.Status, models.TestRun.status_id == models.Status.id)
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
                    "date": month_key,
                    "total_runs": row.total_runs,
                    "status_breakdown": {"Completed": row.passed, "Failed": row.failed},
                    "result_breakdown": {
                        "passed": row.passed,
                        "failed": row.failed,
                        "pending": pending,
                    },
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

    # Base query for test runs — lightweight, no eager loads needed for SQL aggregation
    base_query = db.query(models.TestRun)

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

    # Get aggregated statistics using SQL for better performance
    aggregated_stats = _get_optimized_aggregated_stats(db, base_query, mode, top)

    # Check if there are any results to determine if we should return empty response
    total_runs = 0
    if (
        "overall_summary" in aggregated_stats
        and "total_runs" in aggregated_stats["overall_summary"]
    ):
        total_runs = aggregated_stats["overall_summary"]["total_runs"]
    elif "timeline" in aggregated_stats:
        total_runs = sum(month["total_runs"] for month in aggregated_stats["timeline"])
    elif "status_distribution" in aggregated_stats:
        total_runs = sum(status["count"] for status in aggregated_stats["status_distribution"])
    else:
        # Fallback to a count query if we can't infer total runs from requested mode
        total_runs = base_query.count()

    if total_runs == 0:
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

    # Add percentages to status distribution if present
    if "status_distribution" in aggregated_stats:
        for status_item in aggregated_stats["status_distribution"]:
            status_item["percentage"] = (
                round((status_item["count"] / total_runs) * 100, 2) if total_runs > 0 else 0
            )

    # Build overall summary
    if mode in ["all", "summary"]:
        most_common_status = "unknown"
        if "status_distribution" in aggregated_stats and aggregated_stats["status_distribution"]:
            most_common_status = max(
                aggregated_stats["status_distribution"], key=lambda x: x["count"]
            )["status"]

        overall_summary = {
            "total_runs": total_runs,
            "unique_test_sets": len(aggregated_stats.get("most_run_test_sets", [])),
            "unique_executors": len(aggregated_stats.get("top_executors", [])),
            "most_common_status": most_common_status,
            "pass_rate": aggregated_stats.get("result_distribution", {}).get("pass_rate", 0),
        }
        aggregated_stats["overall_summary"] = overall_summary

    # Build metadata
    available_statuses = [s["status"] for s in aggregated_stats.get("status_distribution", [])]
    available_test_sets = [
        ts["test_set_name"] for ts in aggregated_stats.get("most_run_test_sets", [])
    ]
    available_executors = [e["executor_name"] for e in aggregated_stats.get("top_executors", [])]

    metadata = build_metadata(
        organization_id=organization_id,
        start_date_obj=start_date_obj,
        end_date_obj=end_date_obj,
        months=months,
        mode=mode,
        total_items=total_runs,
        total_test_runs=total_runs,
        available_statuses=available_statuses,
        available_test_sets=available_test_sets,
        available_executors=available_executors,
    )

    # Return data based on mode using shared helper function
    return build_response_data(
        mode,
        MODE_DEFINITIONS,
        status_distribution=aggregated_stats.get("status_distribution", []),
        result_distribution=aggregated_stats.get("result_distribution", {}),
        most_run_test_sets=aggregated_stats.get("most_run_test_sets", []),
        top_executors=aggregated_stats.get("top_executors", []),
        timeline=aggregated_stats.get("timeline", []),
        overall_summary=aggregated_stats.get("overall_summary", {}),
        metadata=metadata,
    )
