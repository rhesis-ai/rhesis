"""Test statistics functions for comprehensive test entity analysis."""

from datetime import datetime
from typing import Dict

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models

from .calculator import StatsCalculator
from .common import build_pass_rate_stats, parse_date_range


def get_test_stats(
    db: Session,
    current_user_organization_id: str | None,
    top: int | None = None,
    months: int = 6,
) -> Dict:
    """
    Get comprehensive statistics about tests.

    Args:
        db: Database session
        current_user_organization_id: Optional organization ID for filtering
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)

    Returns:
        Dict containing:
        - total: Total number of tests
        - stats: Breakdown by dimensions (status, topic, behavior, category, etc.)
        - history: Historical trend data (monthly counts)
        - metadata: Generation timestamp, organization_id, entity_type
    """
    calculator = StatsCalculator(db, organization_id=current_user_organization_id)
    return calculator.get_entity_stats(
        entity_model=models.Test,
        organization_id=current_user_organization_id,
        top=top,
        months=months,
    )


def get_individual_test_stats(
    db: Session,
    test_id: str,
    organization_id: str | None,
    recent_runs_limit: int = 5,
    months: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict:
    """
    Get comprehensive statistics for a single test across all its test runs.

    Analyzes test_result records to provide:
    - Overall pass/fail statistics across all runs
    - Per-metric breakdown of success rates
    - Recent test run details with per-metric results
    - Average execution time

    Args:
        db: Database session
        test_id: ID of the test to analyze
        organization_id: Organization ID for filtering (security)
        recent_runs_limit: Number of recent test runs to include (default: 5)
        months: Number of months to include in historical stats (default: all time)
        start_date: Optional start date (ISO format, overrides months parameter)
        end_date: Optional end date (ISO format, overrides months parameter)

    Returns:
        Dict containing:
        - overall_summary: Total stats, pass/fail counts, pass rate, avg execution time
        - metric_breakdown: Per-metric pass/fail statistics
        - recent_runs: Last N test runs with detailed results
        - metadata: Test ID, generation timestamp, organization_id, date range
    """
    # Parse date range if provided
    start_date_obj = None
    end_date_obj = None
    if start_date or end_date or months:
        months_val = months if months else 999  # Default to all time if not specified
        start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months_val)

    # Base query for test results with eager loading
    base_query = (
        db.query(models.TestResult)
        .options(
            joinedload(models.TestResult.test_run),  # Eager load test run info
        )
        .filter(models.TestResult.test_id == test_id)
    )

    # Apply organization filter (SECURITY CRITICAL)
    if organization_id:
        base_query = base_query.filter(models.TestResult.organization_id == organization_id)

    # Apply date range filters if specified
    if start_date_obj:
        base_query = base_query.filter(models.TestResult.created_at >= start_date_obj)
    if end_date_obj:
        base_query = base_query.filter(models.TestResult.created_at <= end_date_obj)

    # Order by created_at descending for recent runs
    base_query = base_query.order_by(models.TestResult.created_at.desc())

    # Execute query
    test_results = base_query.all()

    if not test_results:
        return _empty_individual_test_stats(
            test_id, organization_id, start_date_obj, end_date_obj, months
        )

    # Initialize statistics
    metric_stats = {}  # metric_name -> {passed: count, failed: count}
    overall_stats = {"passed": 0, "failed": 0}
    execution_times = []
    test_run_results = {}  # test_run_id -> {run_info, overall_passed, execution_time, metrics}

    # Process all test results
    for result in test_results:
        if not result.test_metrics or "metrics" not in result.test_metrics:
            continue

        metrics = result.test_metrics["metrics"]
        if not isinstance(metrics, dict):
            continue

        # Track execution time
        execution_time = result.test_metrics.get("execution_time")
        if execution_time is not None:
            execution_times.append(execution_time)

        # Analyze metrics for this test result
        test_passed_overall = True
        test_metric_results = {}

        for metric_name, metric_data in metrics.items():
            if not isinstance(metric_data, dict) or "is_successful" not in metric_data:
                continue

            is_successful = metric_data["is_successful"]

            # Initialize metric stats if not exists
            if metric_name not in metric_stats:
                metric_stats[metric_name] = {"passed": 0, "failed": 0}

            # Update metric stats
            if is_successful:
                metric_stats[metric_name]["passed"] += 1
            else:
                metric_stats[metric_name]["failed"] += 1
                test_passed_overall = False

            # Store metric result for this test
            test_metric_results[metric_name] = {
                "is_successful": is_successful,
                "score": metric_data.get("score"),
                "reason": metric_data.get("reason") if not is_successful else None,
            }

        # Update overall stats
        if test_passed_overall:
            overall_stats["passed"] += 1
        else:
            overall_stats["failed"] += 1

        # Store test run information for recent runs
        if result.test_run_id:
            run_key = str(result.test_run_id)
            if run_key not in test_run_results:
                test_run = result.test_run if hasattr(result, "test_run") else None
                test_run_results[run_key] = {
                    "test_run_id": run_key,
                    "test_run_name": test_run.name
                    if test_run and test_run.name
                    else f"Test Run {run_key[:8]}",
                    "created_at": test_run.created_at.isoformat()
                    if test_run and test_run.created_at
                    else result.created_at.isoformat()
                    if result.created_at
                    else None,
                    "overall_passed": test_passed_overall,
                    "execution_time_ms": execution_time,
                    "metrics": test_metric_results,
                    # Store timestamp for sorting
                    "_sort_timestamp": test_run.created_at
                    if test_run and test_run.created_at
                    else result.created_at,
                }

    # Calculate overall summary
    total_executions = overall_stats["passed"] + overall_stats["failed"]
    pass_rate = (
        round((overall_stats["passed"] / total_executions) * 100, 2) if total_executions > 0 else 0
    )
    avg_execution_time = (
        round(sum(execution_times) / len(execution_times), 2) if execution_times else 0
    )

    overall_summary = {
        "total_test_runs": len(test_run_results),
        "total_executions": total_executions,
        "passed": overall_stats["passed"],
        "failed": overall_stats["failed"],
        "pass_rate": pass_rate,
        "avg_execution_time_ms": avg_execution_time,
    }

    # Build metric breakdown using shared helper
    metric_breakdown = build_pass_rate_stats(metric_stats)

    # Build recent runs list (sorted by timestamp, most recent first, limited)
    recent_runs = sorted(
        test_run_results.values(),
        key=lambda x: x.get("_sort_timestamp") or datetime.min,
        reverse=True,
    )[:recent_runs_limit]

    # Remove internal sorting key from response
    for run in recent_runs:
        run.pop("_sort_timestamp", None)

    # Build metadata
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "test_id": test_id,
        "organization_id": organization_id,
        "start_date": start_date_obj.isoformat() if start_date_obj else None,
        "end_date": end_date_obj.isoformat() if end_date_obj else None,
        "period": f"Last {months} months" if months else "All time",
        "recent_runs_limit": recent_runs_limit,
        "available_metrics": list(metric_stats.keys()),
    }

    return {
        "overall_summary": overall_summary,
        "metric_breakdown": metric_breakdown,
        "recent_runs": recent_runs,
        "metadata": metadata,
    }


def _empty_individual_test_stats(
    test_id: str,
    organization_id: str | None,
    start_date_obj: datetime | None,
    end_date_obj: datetime | None,
    months: int | None,
) -> Dict:
    """Return empty stats structure when no test results found for individual test."""
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "test_id": test_id,
        "organization_id": organization_id,
        "start_date": start_date_obj.isoformat() if start_date_obj else None,
        "end_date": end_date_obj.isoformat() if end_date_obj else None,
        "period": f"Last {months} months" if months else "All time",
        "available_metrics": [],
    }

    return {
        "overall_summary": {
            "total_test_runs": 0,
            "total_executions": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0,
            "avg_execution_time_ms": 0,
        },
        "metric_breakdown": {},
        "recent_runs": [],
        "metadata": metadata,
    }
