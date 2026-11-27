"""
Evaluation orchestration for prompt responses.

This module handles the coordination of metric evaluation using extracted responses
from endpoint invocations.

Functions:
- evaluate_single_turn_metrics: Evaluate single-turn metrics on a prompt/response pair
- evaluate_multi_turn_metrics: Evaluate conversational metrics on stored traces
- evaluate_prompt_response: Backward compatibility alias for evaluate_single_turn_metrics
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.response_extractor import extract_response_with_fallback
from rhesis.backend.jobs.execution.constants import (
    CONVERSATION_SUMMARY_KEY,
    PENELOPE_EVALUATED_METRICS,
    PENELOPE_GOAL_METRIC_KEY,
    PENELOPE_MESSAGE_KEY,
    TARGET_RESPONSE_KEY,
    TURN_CONTEXT_KEY,
    TURN_METADATA_KEY,
    TURN_TOOL_CALLS_KEY,
)
from rhesis.backend.metrics.applicability import expected_tool_calls
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.metrics.inputs import ResponseTrace, TraceLoader
from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics.expectations import Expectations

if TYPE_CHECKING:
    from rhesis.sdk.metrics import MetricConfig
    from rhesis.sdk.metrics.conversational.types import ConversationHistory

logger = logging.getLogger(__name__)


def _record_discard_reason(stored_output: Dict[str, Any], reason: str) -> None:
    """Attach a user-facing reason to the trace being re-scored, for a discard the UI must
    explain rather than just leave as an unexplained Error status.

    ``stored_output`` is the same dict object that becomes the persisted ``test_output`` --
    ``MultiTurnRunner.run()`` passes it straight through to ``create_test_result_record`` --
    so mutating it here is how the reason reaches storage without widening this function's
    return type to a tuple, which every caller (including tests) would then need to unpack.

    Uses the same ``error`` key as the live path's synthetic response when a contract is
    unusable before the conversation even runs (``output_providers.resolve_multi_turn_contract``
    callers): one field, one meaning, wherever a multi-turn result ends up Error because of the
    evaluation contract. Safe alongside ``response_extractor``'s HTTP-error detection, which
    additionally requires ``status_code >= 400`` -- an ``error`` string alone doesn't trip it.
    """
    stored_output["error"] = reason


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
    if not messages:
        return None
    from rhesis.sdk.metrics.conversational.types import ConversationHistory

    return ConversationHistory.from_messages(messages)


def conversation_trace(conversation_summary: List[Dict[str, Any]]) -> Optional[Trace]:
    """The trace of a stored conversation, one turn per summary entry, or None when empty."""
    history = _build_conversation_history(conversation_summary)
    return Trace.from_conversation(history) if history is not None else None


def conversation_expectations(
    test_config: Dict[str, Any],
    instructions: Optional[str] = None,
    contract: Optional[Dict[str, Any]] = None,
) -> Expectations:
    """What a multi-turn test expects: its goal, restrictions and tool calls, and the
    instructions and contract the goal judge reads."""
    return Expectations(
        goal=test_config.get("goal") or None,
        instructions=instructions,
        restrictions=test_config.get("restrictions") or None,
        contract=contract,
        tool_calls=expected_tool_calls(test_config),
    )


def response_trace(
    prompt_content: str,
    result: Any,
    context: List[str],
    trace_loader: Optional[TraceLoader] = None,
) -> ResponseTrace:
    """The trace of one endpoint response, from its mapped output, tool calls and metadata."""
    mapped = result if isinstance(result, dict) else {}
    return ResponseTrace(
        input=prompt_content,
        output=extract_response_with_fallback(result),
        context=context,
        tool_calls=mapped.get("tool_calls"),
        metadata=mapped.get("metadata"),
        loader=trace_loader,
    )


def evaluate_single_turn_metrics(
    metrics_evaluator: MetricEvaluator,
    prompt_content: str,
    expected_response: str,
    context: List[str],
    result: Dict,
    metrics: List[Union[Dict[str, Any], MetricConfig]],
    test_id: str = "unknown",
    trace_loader: Optional[TraceLoader] = None,
    expected_tool_calls: Optional[List[Dict[str, Any]]] = None,
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
        metrics: List of metric configurations to use for evaluation; the evaluator leaves
            out those judging a conversation
        test_id: Test ID, kept for callers that pass it
        trace_loader: Reads the response's trace, for metrics that declare ``trace``
        expected_tool_calls: The tools the test expects to be called, if it says

    Returns:
        Dictionary containing the evaluation results
    """
    metrics_results = {}

    if not metrics:
        return metrics_results

    try:
        metrics_results = metrics_evaluator.evaluate(
            metrics,
            response_trace(prompt_content, result, context, trace_loader),
            Expectations(response=expected_response, tool_calls=expected_tool_calls),
        )
    except Exception as e:
        logger.warning(f"Error evaluating metrics: {str(e)}")
        # Continue with empty metrics results

    return metrics_results


# Backward compatibility alias
evaluate_prompt_response = evaluate_single_turn_metrics


def stored_contract_for_rescore(
    test: Test, stored_output: Dict[str, Any]
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """The test's stored evaluation contract for scoring a stored conversation.

    ``(False, None)`` when it is stale or unusable -- the reason is recorded on
    ``stored_output`` and nothing should be scored. ``(True, None)`` when the test
    has no contract, which falls back to legacy goal-based scoring.
    """
    from rhesis.backend.app.schemas.evaluation_contract import read_contract
    from rhesis.backend.app.services.test_interpretation import contract_usability

    test_config = test.test_configuration or {}
    # Re-scoring reuses whatever contract is currently stored -- it must not re-interpret here,
    # or two back-to-back re-scores with no intervening change could disagree for no reason.
    # Like `goal`/`instructions` in the caller, this reads the test's CURRENT definition rather
    # than a snapshot from when the trace was produced: a trace's own point-in-time
    # understanding isn't preserved anywhere today, and re-score has always meant "score this
    # trace against the test as it reads today" for those two fields, so the contract follows
    # the same rule rather than becoming the one field that freezes at execution time.
    #
    # That said, the stored contract can itself be BEHIND the test's current wording: unlike
    # `goal`/`instructions`, which are read live and can never be stale, the contract is a
    # cached derivative that only gets refreshed by a live run's `ensure_contract` call. An
    # edit with no live run afterward leaves the old contract sitting on the test, describing
    # wording that no longer exists. Scoring against it would silently apply criteria the
    # author no longer wrote. `is_current_for` is the same freshness check `ensure_contract`
    # uses before deciding whether to re-interpret; re-score can't re-interpret (see above), so
    # a stale contract here can only mean Error, never a fallback to legacy scoring -- that
    # fallback is the exact bug this whole mechanism exists to prevent.
    #
    # Absent entirely (test predates evaluation contracts, or has never executed live) falls
    # through to legacy goal-based scoring, unchanged from before contracts existed.
    stored_contract = read_contract(getattr(test, "test_metadata", None))
    contract_dict: Optional[Dict[str, Any]] = None
    if stored_contract.interpreted_from:
        if not stored_contract.is_current_for(test_config):
            reason = (
                "This test's evaluation contract is out of date -- it no longer matches the "
                "test's current wording. Run the test live, or refresh interpretation, before "
                "re-scoring."
            )
            logger.warning(
                "Test %s's stored evaluation contract is stale for its current wording; "
                "discarding all multi-turn metrics rather than scoring against criteria the "
                "test no longer states.",
                test.id,
            )
            _record_discard_reason(stored_output, reason)
            return False, None
        usable, reason = contract_usability(stored_contract)
        if not usable:
            logger.warning(
                "Test %s has no usable evaluation contract; discarding all multi-turn "
                "metrics rather than reporting an untrustworthy verdict: %s",
                test.id,
                reason,
            )
            _record_discard_reason(stored_output, reason)
            return False, None
        contract_dict = stored_contract.model_dump(mode="json", exclude_none=True)
    return True, contract_dict


def default_goal_metric_config() -> MetricConfig:
    """The judge Penelope builds for itself on a live run, keyed the way it stores it."""
    from rhesis.sdk.metrics import MetricConfig
    from rhesis.sdk.metrics.providers.native.goal_achievement_judge import (
        DEFAULT_GOAL_ACHIEVEMENT_THRESHOLD,
    )

    return MetricConfig(
        class_name="GoalAchievementJudge",
        backend="rhesis",
        name=PENELOPE_GOAL_METRIC_KEY,
        score_type="numeric",
        metric_type="conversational",
        threshold=DEFAULT_GOAL_ACHIEVEMENT_THRESHOLD,
    )


def with_default_goal_metric(metric_configs: List[Any]) -> List[Any]:
    """Score the goal the way a live run does when Penelope is not running.

    A live run ignores any Goal Achievement metric a requirement lists and uses
    Penelope's own judge, so a re-score of the same conversation does the same.
    """
    return [
        mc
        for mc in metric_configs
        if getattr(mc, "class_name", None) not in PENELOPE_EVALUATED_METRICS
    ] + [default_goal_metric_config()]


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
    score_goal: bool = False,
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
        score_goal: Add Penelope's own Goal Achievement judge, for a re-score of a
            test run, where Penelope is not running

    Returns:
        Dictionary of metric evaluation results
    """
    from rhesis.backend.jobs.execution.executors.data import (
        get_test_metrics,
    )
    from rhesis.backend.jobs.execution.executors.metrics import (
        prepare_metric_configs,
    )

    test_config = test.test_configuration or {}
    # GoalAchievementJudge's prompt has a mandatory-instructions block a live run always
    # includes; omitting it here would let a re-score score the same conversation
    # differently from the live run that originally produced it.
    instructions = test_config.get("instructions") or ""

    usable, contract_dict = stored_contract_for_rescore(test, stored_output)
    if not usable:
        return {}

    # Resolve metrics (execution-time > test set > requirement)
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

    metric_configs = prepare_metric_configs(metrics, str(test.id))
    if score_goal:
        metric_configs = with_default_goal_metric(metric_configs)

    if not metric_configs:
        return {}

    from rhesis.backend.app.utils.user_model_utils import text_model_for
    from rhesis.backend.jobs.execution.executors.runners import (
        _build_connector_metric_sender,
    )

    metrics_evaluator = MetricEvaluator(
        model=model,
        text_model=text_model_for(db, user_id, model),
        db=db,
        organization_id=organization_id,
        connector_metric_sender=_build_connector_metric_sender(
            project_id, environment, organization_id
        ),
        require_model=True,
    )

    trace = conversation_trace(stored_output.get(CONVERSATION_SUMMARY_KEY, []))
    if trace is None:
        return {}

    try:
        results = metrics_evaluator.evaluate(
            metric_configs,
            trace,
            conversation_expectations(test_config, instructions, contract_dict),
        )
    except Exception as e:
        logger.warning(f"Error evaluating multi-turn metrics: {str(e)}")
        results = {}

    return results
