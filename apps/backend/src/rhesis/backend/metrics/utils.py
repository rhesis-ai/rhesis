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


def diagnose_invalid_metric(config: Union[Dict[str, Any], MetricConfig]) -> str:
    """
    Diagnose the reason why a metric configuration is invalid.

    Args:
        config: The metric configuration

    Returns:
        A string describing the reason why the metric configuration is invalid
    """
    if config is None:
        return "configuration is None"

    if isinstance(config, MetricConfig):
        missing_fields = []
        if not config.class_name or (
            isinstance(config.class_name, str) and not config.class_name.strip()
        ):
            missing_fields.append("class_name")
        if not config.backend or (isinstance(config.backend, str) and not config.backend.strip()):
            missing_fields.append("backend")
        if missing_fields:
            return f"missing or empty required fields: {', '.join(missing_fields)}"
    elif isinstance(config, dict):
        missing_fields = []
        if (
            "class_name" not in config
            or config["class_name"] is None
            or (isinstance(config["class_name"], str) and not config["class_name"].strip())
        ):
            missing_fields.append("class_name")
        if (
            "backend" not in config
            or config["backend"] is None
            or (isinstance(config["backend"], str) and not config["backend"].strip())
        ):
            missing_fields.append("backend")
        if missing_fields:
            return f"missing or empty required fields: {', '.join(missing_fields)}"
    else:
        return (
            f"invalid configuration type: {type(config).__name__} (expected dict or MetricConfig)"
        )

    return "unknown validation error"
