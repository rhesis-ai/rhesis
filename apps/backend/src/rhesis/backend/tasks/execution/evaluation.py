"""
Evaluation orchestration for prompt responses.

This module handles the coordination of metric evaluation using extracted responses
from endpoint invocations.
"""

from typing import Any, Dict, List, Union

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.sdk.metrics import MetricConfig
from rhesis.backend.metrics.evaluator import MetricEvaluator

from .response_extractor import extract_response_with_fallback


def evaluate_prompt_response(
    metrics_evaluator: MetricEvaluator,
    prompt_content: str,
    expected_response: str,
    context: List[str],
    result: Dict,
    metrics: List[Union[Dict[str, Any], MetricConfig]],
) -> Dict:
    """
    Evaluate prompt response using different metrics.

    Args:
        metrics_evaluator: The metrics evaluator instance
        prompt_content: The original prompt content
        expected_response: The expected response for comparison
        context: List of context strings
        result: The response dictionary from endpoint invocation
        metrics: List of metric configurations to use for evaluation

    Returns:
        Dictionary containing the evaluation results
    """
    metrics_results = {}

    # Extract actual_response using the fallback hierarchy
    actual_response = extract_response_with_fallback(result)

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
