from typing import Dict, List, Any, Union

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.metrics.base import MetricConfig


def evaluate_prompt_response(
    metrics_evaluator: MetricEvaluator,
    prompt_content: str,
    expected_response: str,
    context: List[str],
    result: Dict,
    metrics: List[Union[Dict[str, Any], MetricConfig]],
) -> Dict:
    """Evaluate prompt response using different metrics."""
    metrics_results = {}
    actual_response = result.get("output", "") if result else ""

    try:
        metrics_results = metrics_evaluator.evaluate(
            input_text=prompt_content,
            expected_output=expected_response,
            output_text=actual_response,
            context=context,
            metrics=metrics,
        )
    except Exception as e:
        logger.warning(f"Error evaluating metrics: {str(e)}")
        # Continue with empty metrics results

    return metrics_results 