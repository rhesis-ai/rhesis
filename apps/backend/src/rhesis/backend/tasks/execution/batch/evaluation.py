"""
Metric evaluation for batch tests.
"""

import logging
from typing import Any, Dict, Optional

from rhesis.backend.app.models.test import Test
from rhesis.backend.tasks.execution.batch.context import ExecutionContext
from rhesis.backend.tasks.execution.constants import PENELOPE_EVALUATED_METRICS

logger = logging.getLogger(__name__)


async def evaluate_metrics(
    ctx: ExecutionContext,
    evaluator: Any,
    test: Test,
    test_id: str,
    output: Dict[str, Any],
    prompt_content: str,
    expected_response: str,
    is_multi_turn: bool,
    penelope_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Run async metric evaluation, returning merged results."""
    metrics_results = dict(penelope_metrics)
    try:
        if is_multi_turn:
            metrics_results.update(await _evaluate_multi_turn_metrics(ctx, evaluator, test, output))
        else:
            metrics_results.update(
                await _evaluate_single_turn_metrics(
                    ctx,
                    evaluator,
                    test,
                    output,
                    prompt_content,
                    expected_response,
                )
            )
    except Exception as e:
        logger.error(f"[BATCH] Metric eval failed for {test_id}: {e}", exc_info=True)
    return metrics_results


async def _evaluate_multi_turn_metrics(
    ctx: ExecutionContext,
    evaluator: Any,
    test: Test,
    output: Dict[str, Any],
) -> Dict[str, Any]:
    from rhesis.backend.tasks.execution.constants import CONVERSATION_SUMMARY_KEY
    from rhesis.backend.tasks.execution.evaluation import _build_conversation_history

    conversation_summary = output.get(CONVERSATION_SUMMARY_KEY, [])
    conversation_history = _build_conversation_history(conversation_summary)
    conversation_text = conversation_history.format_conversation() if conversation_history else ""

    test_config_data = test.test_configuration or {}
    goal = test_config_data.get("goal", "")

    filtered_configs = [
        mc for mc in ctx.metric_configs if mc.class_name not in PENELOPE_EVALUATED_METRICS
    ]

    if not filtered_configs:
        return {}

    return await evaluator.a_evaluate(
        input_text=goal,
        output_text=conversation_text.strip(),
        expected_output="",
        context=[],
        metrics=filtered_configs,
        conversation_history=conversation_history,
    )


async def _evaluate_single_turn_metrics(
    ctx: ExecutionContext,
    evaluator: Any,
    test: Any,
    output: Dict[str, Any],
    prompt_content: str,
    expected_response: str,
) -> Dict[str, Any]:
    from rhesis.backend.tasks.execution.response_extractor import (
        extract_response_with_fallback,
    )

    actual_response = extract_response_with_fallback(output)
    metadata = output.get("metadata") if isinstance(output, dict) else None
    tool_calls = output.get("tool_calls") if isinstance(output, dict) else None

    # Inject probe-level notes (e.g. trigger strings for Garak probe-coupled detectors)
    # directly into the metric configs so the metric has them at construction time.
    # This avoids threading probe context through the generic evaluator interface.
    garak_notes = (test.test_metadata or {}).get("garak_notes") if test else None
    metric_configs = _inject_probe_notes(ctx.metric_configs, garak_notes)

    return await evaluator.a_evaluate(
        input_text=prompt_content,
        output_text=actual_response,
        expected_output=expected_response,
        context=[],
        metrics=metric_configs,
        metadata=metadata,
        tool_calls=tool_calls,
    )


def _inject_probe_notes(metric_configs: list, probe_notes: Optional[Dict[str, Any]]) -> list:
    """
    Return a copy of metric_configs with probe_notes merged into the parameters
    of any Garak metric that is registered as requiring probe context.

    Only injects when probe_notes is non-empty, and never overwrites an existing
    probe_notes value already present in MetricConfig.parameters (non-destructive).
    Returns the original list unchanged when there is nothing to inject.
    """
    if not probe_notes:
        return metric_configs

    from rhesis.sdk.metrics.providers.garak.registry import is_context_required

    result = []
    for config in metric_configs:
        evaluation_prompt = getattr(config, "evaluation_prompt", None)
        if evaluation_prompt and is_context_required(evaluation_prompt):
            existing_params = config.parameters or {}
            if "probe_notes" not in existing_params:
                import dataclasses

                updated_params = {**existing_params, "probe_notes": probe_notes}
                config = dataclasses.replace(config, parameters=updated_params)
        result.append(config)
    return result
