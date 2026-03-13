"""
Evaluation orchestration for prompt responses.

This module handles the coordination of metric evaluation using extracted responses
from endpoint invocations.

Functions:
- evaluate_single_turn_metrics: Evaluate single-turn metrics on a prompt/response pair
- evaluate_multi_turn_metrics: Evaluate conversational metrics on stored traces
- evaluate_prompt_response: Backward compatibility alias for evaluate_single_turn_metrics
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.execution.constants import (
    CONVERSATION_SUMMARY_KEY,
    PENELOPE_MESSAGE_KEY,
    TARGET_RESPONSE_KEY,
    TURN_CONTEXT_KEY,
    TURN_METADATA_KEY,
    TURN_TOOL_CALLS_KEY,
    MetricScope,
)
from rhesis.sdk.metrics import MetricConfig
from rhesis.sdk.metrics.conversational.types import ConversationHistory

from .response_extractor import extract_response_with_fallback

logger = logging.getLogger(__name__)


def _build_conversation_history(
    conversation_summary: List[Dict[str, Any]],
) -> Optional[ConversationHistory]:
    """
    Build a ConversationHistory from a Penelope conversation_summary list.

    Each entry in conversation_summary maps to one user+assistant exchange:
    - ``penelope_message``  → user role
    - ``target_response``   → assistant role
    - ``context``           → per-turn retrieval context (optional)
    - ``metadata``          → per-turn structured metadata (optional)
    - ``tool_calls``        → per-turn tool calls by the endpoint (optional)
    """
    messages: List[Dict[str, Any]] = []
    for turn in conversation_summary:
        penelope_msg = turn.get(PENELOPE_MESSAGE_KEY, "")
        target_resp = turn.get(TARGET_RESPONSE_KEY, "")
        assistant_context = turn.get(TURN_CONTEXT_KEY)
        assistant_metadata = turn.get(TURN_METADATA_KEY)
        assistant_tool_calls = turn.get(TURN_TOOL_CALLS_KEY)
        if penelope_msg:
            messages.append({"role": "user", "content": penelope_msg})
        if target_resp:
            asst_msg: Dict[str, Any] = {"role": "assistant", "content": target_resp}
            if assistant_context is not None:
                asst_msg["context"] = assistant_context
            if assistant_metadata is not None:
                asst_msg["metadata"] = assistant_metadata
            if assistant_tool_calls is not None:
                asst_msg["tool_calls"] = assistant_tool_calls
            messages.append(asst_msg)
    return ConversationHistory.from_messages(messages) if messages else None


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
    metadata = result.get("metadata") if isinstance(result, dict) else None
    tool_calls = result.get("tool_calls") if isinstance(result, dict) else None

    try:
        metrics_results = metrics_evaluator.evaluate(
            input_text=prompt_content,
            expected_output=expected_response,
            output_text=actual_response,
            context=context,
            metrics=metrics,
            metadata=metadata,
            tool_calls=tool_calls,
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
    exclude_class_names: Optional[Set[str]] = None,
    project_id: Optional[str] = None,
    environment: Optional[str] = None,
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
        exclude_class_names: Optional set of metric class names to exclude
            (e.g., {"GoalAchievementJudge"} when Penelope already evaluated it)

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

    # Exclude metrics already evaluated (e.g., by Penelope)
    if exclude_class_names:
        metrics = [m for m in metrics if m.class_name not in exclude_class_names]

    metric_configs = prepare_metric_configs(metrics, str(test.id), scope=MetricScope.MULTI_TURN)

    if not metric_configs:
        return {}

    from rhesis.backend.tasks.execution.executors.runners import (
        _build_connector_metric_sender,
    )

    metrics_evaluator = MetricEvaluator(
        model=model,
        db=db,
        organization_id=organization_id,
        connector_metric_sender=_build_connector_metric_sender(project_id, environment),
    )

    conversation_summary = stored_output.get(CONVERSATION_SUMMARY_KEY, [])
    conversation_history = _build_conversation_history(conversation_summary)
    conversation_text = conversation_history.to_text() if conversation_history else ""

    try:
        results = metrics_evaluator.evaluate(
            input_text=goal,
            output_text=conversation_text.strip(),
            expected_output="",
            context=[],
            metrics=metric_configs,
            conversation_history=conversation_history,
        )
    except Exception as e:
        logger.warning(f"Error evaluating multi-turn metrics: {str(e)}")
        results = {}

    return results
