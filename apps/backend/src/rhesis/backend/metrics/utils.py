from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.metrics import MetricConfig


def run_evaluation(
    input_text: str,
    output_text: str,
    expected_output: Optional[str],
    context: List[str],
    metrics: List[Union[Dict[str, Any], MetricConfig]],
    max_workers: int = 5,
) -> Dict[str, Any]:
    """
    Helper function to run the metric evaluation using MetricEvaluator.

    Args:
        input_text: The input query or question
        output_text: The actual output from the LLM
        expected_output: The expected or reference output
        context: List of context strings used for the response
        metrics: List of metric configurations (MetricConfig objects or dictionaries)
        max_workers: Maximum number of parallel workers

    Returns:
        Dictionary of metric results
    """
    # Lazy import to avoid circular dependencies
    from rhesis.backend.metrics.evaluator import MetricEvaluator

    evaluator = MetricEvaluator()
    return evaluator.evaluate(
        input_text=input_text,
        output_text=output_text,
        expected_output=expected_output,
        context=context,
        metrics=metrics,
        max_workers=max_workers,
    )


def diagnose_invalid_metric(config: MetricConfig) -> str:
    """
    Diagnose the reason why a metric configuration is invalid.

    Args:
        config: The metric configuration (must be MetricConfig; normalize before calling).

    Returns:
        A string describing the reason why the metric configuration is invalid
    """
    if config is None:
        return "configuration is None"

    missing_fields = []
    if not config.class_name or (
        isinstance(config.class_name, str) and not config.class_name.strip()
    ):
        missing_fields.append("class_name")
    backend_val = getattr(config.backend, "value", config.backend)
    if not backend_val or (
        isinstance(backend_val, str) and not backend_val.strip()
    ):
        missing_fields.append("backend")
    if missing_fields:
        return f"missing or empty required fields: {', '.join(missing_fields)}"

    return "unknown validation error"
