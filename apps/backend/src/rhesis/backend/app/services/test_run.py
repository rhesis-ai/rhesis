import csv
import uuid
from io import StringIO
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import crud


def get_test_results_for_test_run(
    db: Session, test_run_id: uuid.UUID, organization_id: str = None
) -> List[Dict[str, Any]]:
    """
    Get all test results for a test run with related data for CSV export.

    Args:
        db: Database session
        test_run_id: UUID of the test run
        organization_id: Organization ID for security filtering

    Returns:
        List of dictionaries containing test result data
    """
    # First check if test run exists
    test_run = crud.get_test_run(db, test_run_id, organization_id=organization_id)
    if not test_run:
        raise ValueError("Test Run not found")

    # Get test results for this test run with pagination to handle large result sets
    filter_str = f"test_run_id eq {test_run_id}"
    all_test_results = []
    skip = 0
    limit = 100  # Use maximum allowed limit

    while True:
        test_results_batch = crud.get_test_results(
            db, skip=skip, limit=limit, filter=filter_str, organization_id=organization_id
        )
        if not test_results_batch:
            break
        all_test_results.extend(test_results_batch)
        if len(test_results_batch) < limit:
            # Last batch, no more results
            break
        skip += limit

    if not all_test_results:
        raise ValueError("No test results found for this test run")

    # Get behaviors and metrics for this test run with organization filtering (SECURITY CRITICAL)
    behaviors = crud.get_test_run_behaviors(
        db, test_run_id, organization_id=str(test_run.organization_id)
    )

    # Create a mapping of behavior_id to behavior with metrics
    behavior_map = {}
    for behavior in behaviors:
        # Get metrics for this behavior (use default limit to stay within bounds)
        # SECURITY: Pass organization_id from test_run to prevent cross-tenant access
        metrics = crud.get_behavior_metrics(
            db, behavior.id, organization_id=str(test_run.organization_id)
        )
        behavior_map[behavior.id] = {"behavior": behavior, "metrics": metrics}

    # Process test results into CSV format
    csv_data = []

    for result in all_test_results:
        # Get related data with organization filtering
        test = (
            crud.get_test(db, result.test_id, organization_id=organization_id)
            if result.test_id
            else None
        )
        prompt = (
            crud.get_prompt(db, result.prompt_id, organization_id=organization_id)
            if result.prompt_id
            else None
        )

        # Base row data
        row = {
            "test_id": str(result.test_id) if result.test_id else "N/A",
            "prompt_content": prompt.content if prompt else "N/A",
            "response": result.test_output.get("output", "N/A") if result.test_output else "N/A",
            "created_at": result.created_at.isoformat() if result.created_at else "N/A",
        }

        # Add behavior metrics columns
        test_metrics = result.test_metrics.get("metrics", {}) if result.test_metrics else {}

        for behavior_id, behavior_data in behavior_map.items():
            behavior = behavior_data["behavior"]
            metrics = behavior_data["metrics"]

            for metric in metrics:
                metric_name = metric.name
                column_name = f"{behavior.name}_{metric_name}"

                # Get metric result
                metric_result = test_metrics.get(metric_name)
                if metric_result:
                    status = "Pass" if metric_result.get("is_successful") else "Fail"
                    score = metric_result.get("score", "N/A")
                    threshold = metric_result.get("threshold")
                    reference_score = metric_result.get("reference_score")
                    reason = metric_result.get("reason", "")

                    # Format based on metric type
                    if reference_score is not None:
                        # Binary/categorical metric
                        value = f"{status} ({score} vs {reference_score})"
                    elif threshold is not None:
                        # Numeric metric
                        value = f"{status} ({score}/{threshold})"
                    else:
                        # Generic metric
                        value = f"{status} ({score})"

                    if reason:
                        value += f" - {reason}"

                    row[column_name] = value
                else:
                    row[column_name] = "N/A"

        csv_data.append(row)

    return csv_data


def test_run_results_to_csv(test_results_data: List[Dict[str, Any]]) -> str:
    """
    Convert test run results data to CSV format.

    Args:
        test_results_data: List of dictionaries containing test result data

    Returns:
        CSV string
    """
    if not test_results_data:
        raise ValueError("No test results data to convert to CSV")

    # Get all unique column names
    all_columns = set()
    for row in test_results_data:
        all_columns.update(row.keys())

    # Order columns: base columns first, then behavior metrics
    base_columns = ["test_id", "prompt_content", "response", "created_at"]
    metric_columns = sorted([col for col in all_columns if col not in base_columns])
    ordered_columns = base_columns + metric_columns

    # Generate CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=ordered_columns, extrasaction="ignore")

    writer.writeheader()
    for row in test_results_data:
        writer.writerow(row)

    return output.getvalue()
