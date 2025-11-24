"""Metrics processing and evaluation utilities."""

from typing import Any, Dict, List, Optional

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ResultStatus
from rhesis.backend.tasks.execution.constants import MetricScope


def filter_metrics_by_scope(metrics: List, scope: MetricScope, test_id: str) -> List:
    """
    Filter metrics by scope (Single-Turn or Multi-Turn).

    Only includes metrics that explicitly have the requested scope in their metric_scope array.
    Metrics without a metric_scope field are excluded.

    Args:
        metrics: List of Metric models
        scope: MetricScope enum value (MetricScope.SINGLE_TURN or MetricScope.MULTI_TURN)
        test_id: Test ID for logging

    Returns:
        List of metrics that support the specified scope
    """
    if not scope:
        return metrics

    filtered_metrics = []
    filtered_out_count = 0
    no_scope_count = 0

    # Get the string value from the enum for comparison with DB values
    scope_value = scope.value

    logger.debug(f"Filtering metrics for test {test_id} with scope: {scope_value}")

    for metric in metrics:
        # Check if metric has metric_scope attribute (stored as array in DB)
        metric_scope = getattr(metric, "metric_scope", None)

        logger.debug(
            f"Checking metric '{metric.name}' (class: {metric.class_name}): "
            f"metric_scope={metric_scope}"
        )

        # Strict filtering: only include metrics with explicit scope
        if not metric_scope or (isinstance(metric_scope, list) and len(metric_scope) == 0):
            # Exclude metrics without scope definition
            no_scope_count += 1
            filtered_out_count += 1
            logger.warning(
                f"Excluded metric '{metric.name}' (class: {metric.class_name}) "
                f"for test {test_id}: metric_scope is not defined. "
                f"Please update the database to set metric_scope for this metric."
            )
            continue

        # metric_scope must be a list/array in the database
        if isinstance(metric_scope, list):
            # Check if the desired scope is in the metric's supported scopes
            if scope_value in metric_scope:
                filtered_metrics.append(metric)
                logger.debug(
                    f"Including metric '{metric.name}': scope {scope_value} found in {metric_scope}"
                )
            else:
                filtered_out_count += 1
                logger.debug(
                    f"Excluded metric '{metric.name}' (class: {metric.class_name}) "
                    f"for test {test_id}: requires scope {metric_scope}, "
                    f"test requires {scope_value}"
                )
        else:
            # Invalid metric_scope type - exclude it
            filtered_out_count += 1
            logger.warning(
                f"Excluded metric '{metric.name}' (class: {metric.class_name}) "
                f"for test {test_id}: metric_scope has invalid type {type(metric_scope)}. "
                f"Expected list/array."
            )

    if no_scope_count > 0:
        logger.warning(
            f"Excluded {no_scope_count} metrics without metric_scope for test {test_id}. "
            f"Please update the database to set metric_scope for all metrics."
        )

    if filtered_out_count > 0:
        logger.info(
            f"Filtered out {filtered_out_count} metrics for test {test_id} "
            f"(test scope: {scope_value})"
        )

    logger.info(
        f"Scope filtering complete for test {test_id}: "
        f"{len(filtered_metrics)}/{len(metrics)} metrics included for scope {scope_value}"
    )

    return filtered_metrics


def prepare_metric_configs(
    metrics: List,
    test_id: str,
    scope: Optional[MetricScope] = None,
) -> List:
    """
    Validate and filter metric models.

    The evaluator accepts Metric models directly. This function validates that
    models have required fields and filters out any that are invalid or don't
    match the specified scope.

    Args:
        metrics: List of Metric models
        test_id: Test ID for logging
        scope: Optional MetricScope enum to filter by

    Returns:
        List of valid Metric models that match the scope
    """

    # Validate that each metric has required fields
    valid_metrics = []
    invalid_count = 0

    for i, metric in enumerate(metrics):
        # All metrics should be Metric model instances
        if not hasattr(metric, "class_name"):
            logger.warning(f"Metric {i} has unexpected type: {type(metric)}")
            invalid_count += 1
            continue

        if not metric.class_name:
            invalid_count += 1
            logger.warning(f"Skipped metric {i} for test {test_id}: missing class_name")
            continue

        valid_metrics.append(metric)

    if invalid_count > 0:
        logger.warning(f"Skipped {invalid_count} invalid metrics for test {test_id}")

    # Filter by scope if specified
    if scope:
        valid_metrics = filter_metrics_by_scope(valid_metrics, scope, test_id)

    if not valid_metrics:
        logger.warning(
            f"No valid metrics found for test {test_id}, proceeding without metric evaluation"
        )

    return valid_metrics


def determine_status_from_metrics(metrics: Dict[str, Any]) -> str:
    """
    Determine test status from metric results.

    Returns:
        "Pass" if all metrics successful
        "Fail" if any metric failed
        "Error" if no valid metrics
    """
    if not metrics or not isinstance(metrics, dict):
        return ResultStatus.ERROR.value

    # Check if all metrics passed
    all_passed = True
    has_metrics = False

    for metric_name, metric_result in metrics.items():
        if isinstance(metric_result, dict):
            has_metrics = True
            is_successful = metric_result.get("is_successful", False)
            if not is_successful:
                all_passed = False
                break

    if not has_metrics:
        return ResultStatus.ERROR.value

    return ResultStatus.PASS.value if all_passed else ResultStatus.FAIL.value
