"""
Evaluation orchestration for prompt responses.

This module handles the coordination of metric evaluation using extracted responses
from endpoint invocations.

Functions:
- evaluate_single_turn_metrics: Evaluate single-turn metrics on a prompt/response pair
- evaluate_multi_turn_metrics: Evaluate conversational metrics on stored traces
- evaluate_prompt_response: Backward compatibility alias for evaluate_single_turn_metrics
"""

from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.execution.constants import MetricScope
from rhesis.sdk.metrics import MetricConfig

from .response_extractor import extract_response_with_fallback


def evaluate_single_turn_metrics(
    metrics_evaluator: MetricEvaluator,
    prompt_content: str,
    expected_response: str,
    context: List[str],
    result: Dict,
    metrics: List[Union[Dict[str, Any], MetricConfig]],
) -> Dict:
    """
    Evaluate single-turn metrics on a prompt/response pair.

    Renamed from evaluate_prompt_response() for naming consistency
    with evaluate_multi_turn_metrics().

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


# Backward compatibility alias
evaluate_prompt_response = evaluate_single_turn_metrics


def evaluate_multi_turn_metrics(
    stored_output: Dict[str, Any],
    test: Test,
    db: Session,
    organization_id: str,
    user_id: Optional[str],
    model: Any,
    test_set: Any = None,
    test_configuration: Any = None,
) -> Dict[str, Any]:
    """Evaluate conversational metrics on a stored Penelope trace or conversation.

    The multi-turn counterpart to evaluate_single_turn_metrics().
    Used when re-scoring (TestResultOutput) or evaluating traces (TraceOutput)
    where Penelope is not running and metrics need standalone evaluation.

    Args:
        stored_output: The stored Penelope trace or conversation data
        test: Test model instance
        db: Database session
        organization_id: Organization ID for multi-tenant safety
        user_id: User ID (optional)
        model: LLM model for metric evaluation
        test_set: Optional TestSet model for metric override
        test_configuration: Optional TestConfiguration for execution-time override

    Returns:
        Dictionary of metric evaluation results
    """
    from rhesis.backend.tasks.execution.executors.data import (
        get_test_metrics,
    )
    from rhesis.backend.tasks.execution.executors.metrics import (
        prepare_metric_configs,
    )

    test_config = test.test_configuration or {}
    goal = test_config.get("goal", "")

    # Resolve metrics (execution-time > test set > behavior)
    metrics = get_test_metrics(
        test,
        db,
        organization_id,
        user_id,
        test_set=test_set,
        test_configuration=test_configuration,
    )
    metric_configs = prepare_metric_configs(metrics, str(test.id), scope=MetricScope.MULTI_TURN)

    if not metric_configs:
        return {}

    # Evaluate each metric on the conversation using the MetricEvaluator
    # For multi-turn, we reconstruct the conversation as a single prompt/response
    # pair and evaluate with the standard evaluator pipeline.
    # This approach reuses the existing evaluator infrastructure.
    metrics_evaluator = MetricEvaluator(model=model, db=db, organization_id=organization_id)

    # Build a prompt/response pair from the conversation for evaluation
    conversation_text = ""
    for turn in stored_output.get("conversation_summary", []):
        penelope_msg = turn.get("penelope_message", "")
        target_resp = turn.get("target_response", "")
        if penelope_msg:
            conversation_text += f"User: {penelope_msg}\n"
        if target_resp:
            conversation_text += f"Assistant: {target_resp}\n"

    try:
        results = metrics_evaluator.evaluate(
            input_text=goal,
            output_text=conversation_text.strip(),
            expected_output="",
            context=[],
            metrics=metric_configs,
        )
    except Exception as e:
        logger.warning(f"Error evaluating multi-turn metrics: {str(e)}")
        results = {}

    return results
