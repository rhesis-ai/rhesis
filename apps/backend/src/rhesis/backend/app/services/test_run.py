import csv
import uuid
from io import StringIO
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.logging.rhesis_logger import logger


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


def rescore_test_run(
    db: Session,
    reference_test_run_id: str,
    current_user: models.User,
    metrics: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a new test run that re-scores an existing one.

    No endpoints are invoked -- only metric evaluation on stored outputs.

    Args:
        db: Database session
        reference_test_run_id: UUID string of the test run to re-score
        current_user: Current authenticated user
        metrics: Optional list of execution-time metrics to use.
            Each dict should have: id, name, and optionally scope.
            If None, re-uses the original test run's metrics.

    Returns:
        Dict containing new test_run_id and status

    Raises:
        ValueError: If the reference test run is not found
    """
    org_id = str(current_user.organization_id)
    uid = str(current_user.id)

    # 1. Load the reference test run
    ref_run = crud.get_test_run(
        db,
        test_run_id=uuid.UUID(reference_test_run_id),
        organization_id=org_id,
        user_id=uid,
    )
    if not ref_run:
        raise ValueError(f"Test run {reference_test_run_id} not found")

    ref_config = ref_run.test_configuration
    if not ref_config:
        raise ValueError(f"Test run {reference_test_run_id} has no test configuration")

    # 2. Build attributes for the new test configuration
    attributes = {
        "reference_test_run_id": reference_test_run_id,
        "is_rescore": True,
        "execution_mode": "Parallel",
    }

    # Add metrics override if provided
    if metrics:
        attributes["metrics"] = metrics
        from rhesis.backend.app.schemas.test_set import MetricsSource

        attributes["metrics_source"] = MetricsSource.EXECUTION_TIME.value
        logger.debug(f"Rescore using {len(metrics)} execution-time metrics")

    # 3. Create new TestConfiguration pointing to same endpoint/test_set
    new_config = schemas.TestConfigurationCreate(
        endpoint_id=ref_config.endpoint_id,
        test_set_id=ref_config.test_set_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        attributes=attributes,
    )
    db_new_config = crud.create_test_configuration(
        db=db,
        test_configuration=new_config,
        organization_id=org_id,
        user_id=uid,
    )
    new_config_id = str(db_new_config.id)
    logger.info(
        f"Created rescore test configuration {new_config_id} "
        f"for reference run {reference_test_run_id}"
    )

    # 4. Submit for execution via the task launcher
    from rhesis.backend.tasks import task_launcher
    from rhesis.backend.tasks.test_configuration import (
        execute_test_configuration,
    )

    result = task_launcher(
        execute_test_configuration,
        new_config_id,
        current_user=current_user,
    )

    logger.info(f"Rescore submitted for reference run {reference_test_run_id}, task {result.id}")

    return {
        "status": "submitted",
        "message": (f"Re-scoring test run {reference_test_run_id} with new metrics"),
        "test_configuration_id": new_config_id,
        "reference_test_run_id": reference_test_run_id,
        "task_id": result.id,
    }
