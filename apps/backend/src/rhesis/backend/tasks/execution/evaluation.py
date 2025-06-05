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
    
    # Debug: Log the result structure
    logger.info(f"DEBUG: Result structure for evaluation: {result}")
    
    # Handle the new error structure from REST invoker
    if result and result.get("error", False):
        # If there's an error, use the error message as the actual response
        actual_response = result.get("message", "Unknown error occurred")
        logger.info(f"Using error message as response for evaluation: {actual_response}")
    else:
        # For successful responses, extract the output
        if result and not result.get("error", False):
            # New success structure: {"error": false, "data": {...}}
            actual_response = result.get("data", {}).get("output", "") if isinstance(result.get("data"), dict) else result.get("data", "")
            # Fallback to old structure if data doesn't contain output
            if not actual_response:
                actual_response = result.get("output", "") if result else ""
        else:
            # Fallback for old structure or empty result
            actual_response = result.get("output", "") if result else ""

    # Debug: Log the extracted actual_response
    logger.info(f"DEBUG: Extracted actual_response for metrics: '{actual_response}' (type: {type(actual_response)})")

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