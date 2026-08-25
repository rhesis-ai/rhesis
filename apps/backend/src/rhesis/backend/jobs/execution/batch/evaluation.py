"""
Metric evaluation for batch tests.
"""

import logging
from typing import Any, Callable, Dict, Optional

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.response_extractor import (
    get_http_error_status_code,
    has_http_error_in_result,
)
from rhesis.backend.jobs.execution.batch.context import ExecutionContext
from rhesis.backend.jobs.execution.constants import PENELOPE_EVALUATED_METRICS, MetricScope
from rhesis.backend.jobs.execution.evaluation import filter_configs_by_scope

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
    on_emit: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Run async metric evaluation, returning merged results."""
    # HTTP errors are not model answers; do not score metrics against them.
    if has_http_error_in_result(output):
        status_code = get_http_error_status_code(output)
        logger.info(
            f"[BATCH] HTTP error for test {test_id} (status_code={status_code}); skipping metrics"
        )
        return {}

    on_metric_complete = None
    if on_emit:

        def on_metric_complete(metric_key: str, result: Dict[str, Any]) -> None:
            error = result.get("error")
            if error:
                on_emit(f"  {metric_key}: error ({error})")
                return
            passed = result.get("is_successful")
            score = result.get("score", "?")
            label = "passed" if passed else ("failed" if passed is False else "scored")
            on_emit(f"  {metric_key}: {label} ({score})")

    metrics_results = dict(penelope_metrics)
    test_metric_configs = ctx.get_metric_configs_for_test(test_id)
    try:
        if is_multi_turn:
            metrics_results.update(
                await _evaluate_multi_turn_metrics(
                    ctx,
                    evaluator,
                    test,
                    output,
                    test_metric_configs,
                    on_metric_complete=on_metric_complete,
                )
            )
        else:
            metrics_results.update(
                await _evaluate_single_turn_metrics(
                    ctx,
                    evaluator,
                    test,
                    output,
                    prompt_content,
                    expected_response,
                    test_metric_configs,
                    on_metric_complete=on_metric_complete,
                )
            )
    except Exception as e:
        logger.error(f"[BATCH] Metric eval failed for {test_id}: {e}", exc_info=True)
        if on_emit:
            on_emit(f"  Metric evaluation failed: {e}")
    return metrics_results


async def _evaluate_multi_turn_metrics(
    _ctx: ExecutionContext,
    evaluator: Any,
    test: Test,
    output: Dict[str, Any],
    metric_configs: list,
    on_metric_complete: Any = None,
) -> Dict[str, Any]:
    from rhesis.backend.jobs.execution.constants import CONVERSATION_SUMMARY_KEY
    from rhesis.backend.jobs.execution.evaluation import (
        _build_conversation_history,
        _collect_conversation_context,
    )

    conversation_summary = output.get(CONVERSATION_SUMMARY_KEY, [])
    conversation_history = _build_conversation_history(conversation_summary)
    conversation_text = conversation_history.format_conversation() if conversation_history else ""

    test_config_data = test.test_configuration or {}
    goal = test_config_data.get("goal", "")

    # The batch prefetch cannot scope-filter (one shared config list may serve a
    # mixed-type test set), so it happens here. Without it, Single-Turn metrics
    # ran against conversations with the context=[] passed below and failed by
    # construction, dragging down the pass rate.
    filtered_configs = filter_configs_by_scope(
        metric_configs, MetricScope.MULTI_TURN, str(getattr(test, "id", "?"))
    )
    filtered_configs = [
        mc for mc in filtered_configs if mc.class_name not in PENELOPE_EVALUATED_METRICS
    ]

    if not filtered_configs:
        return {}

    # Empty conversation summary means there is nothing to evaluate in a multi-turn
    # context — return early rather than passing conversation_history=None to metrics
    # that may accept it (including those with metric_scope=None or mixed scopes).
    if conversation_history is None:
        return {}

    return await evaluator.a_evaluate(
        input_text=goal,
        output_text=conversation_text.strip(),
        expected_output="",
        context=_collect_conversation_context(conversation_summary),
        metrics=filtered_configs,
        conversation_history=conversation_history,
        on_metric_complete=on_metric_complete,
    )


async def _evaluate_single_turn_metrics(
    _ctx: ExecutionContext,
    evaluator: Any,
    test: Any,
    output: Dict[str, Any],
    prompt_content: str,
    expected_response: str,
    metric_configs: list,
    on_metric_complete: Any = None,
) -> Dict[str, Any]:
    from rhesis.backend.app.utils.response_extractor import (
        extract_response_with_fallback,
        normalize_context_to_list,
    )

    actual_response = extract_response_with_fallback(output)
    metadata = output.get("metadata") if isinstance(output, dict) else None
    tool_calls = output.get("tool_calls") if isinstance(output, dict) else None
    raw_context = output.get("context") if isinstance(output, dict) else None
    context = normalize_context_to_list(raw_context)

    # Inject probe-level notes (e.g. trigger strings for Garak probe-coupled detectors)
    # directly into the metric configs so the metric has them at construction time.
    # This avoids threading probe context through the generic evaluator interface.
    garak_notes = (test.test_metadata or {}).get("garak_notes") if test else None
    metric_configs = _inject_probe_notes(metric_configs, garak_notes)

    # Keep only metrics scoped to Single-Turn. This previously dropped just the
    # Multi-Turn-*only* ones, which let undeclared-scope metrics through and had
    # no counterpart on the multi-turn side.
    metric_configs = filter_configs_by_scope(
        metric_configs, MetricScope.SINGLE_TURN, str(getattr(test, "id", "?"))
    )

    if not metric_configs:
        return {}

    return await evaluator.a_evaluate(
        input_text=prompt_content,
        output_text=actual_response,
        expected_output=expected_response,
        context=context,
        metrics=metric_configs,
        metadata=metadata,
        tool_calls=tool_calls,
        on_metric_complete=on_metric_complete,
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
