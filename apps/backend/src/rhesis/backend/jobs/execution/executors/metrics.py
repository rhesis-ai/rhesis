"""Metrics processing and evaluation utilities."""

import logging
from typing import Any, Dict, List

from rhesis.backend.app.outcomes import (
    classify_metrics,
    outcome_of,
    outcome_to_test_result_status_name,
)

logger = logging.getLogger(__name__)


def prepare_metric_configs(
    metrics: List,
    test_id: str,
) -> List:
    """
    Validate metric models.

    The evaluator accepts Metric models directly. This function filters out models
    missing required fields; the evaluator leaves out the metrics that don't apply
    to the test.

    Args:
        metrics: List of Metric models
        test_id: Test ID for logging

    Returns:
        List of valid Metric models
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

    if not valid_metrics:
        logger.warning(
            f"No valid metrics found for test {test_id}, proceeding without metric evaluation"
        )

    return valid_metrics


def determine_status_from_metrics(metrics: Dict[str, Any]) -> str:
    """
    Determine test status from metric results.

    Thin wrapper over the single classifier in app/outcomes.py -- see
    playground/outcome-model/inventory.md section 4.1 for the seven
    duplicated copies of this rule this one replaces. No HTTP-error
    awareness: this call site's caller never persists a TestResult row (a
    no-DB preview response), so there is no status_id to correct after the
    fact if the caller later learns the invocation itself failed.

    Returns:
        "Pass" if all metrics passed, "Fail" if any definitively failed,
        "Inconclusive" if the only disagreement is a metric with no
        pass/fail verdict to give, "Error" if nothing could be evaluated
        (no metrics, or a metric crashed while evaluating).
    """
    execution, verdict = classify_metrics(metrics)
    return outcome_to_test_result_status_name(outcome_of(execution, verdict))
