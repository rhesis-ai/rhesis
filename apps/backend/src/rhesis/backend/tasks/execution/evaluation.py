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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.response_extractor import extract_response_with_fallback
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


def _scope_values(mc: Any) -> List[str]:
    """Return a metric config's declared scopes as plain strings.

    Accepts MetricConfig objects and raw dicts, and tolerates MetricScope enums,
    bare strings, or a mis-shaped non-list value (treated as undeclared).
    """
    scope = mc.get("metric_scope") if isinstance(mc, dict) else getattr(mc, "metric_scope", None)
    if not scope or not isinstance(scope, (list, tuple, set)):
        return []
    return [getattr(s, "value", s) for s in scope]


def filter_configs_by_scope(
    metric_configs: List[Any],
    scope: MetricScope,
    test_id: str,
) -> List[Any]:
    """Keep only the configs that declare support for ``scope``.

    Config-level counterpart to
    :func:`~rhesis.backend.tasks.execution.executors.metrics.filter_metrics_by_scope`,
    which operates on ORM Metric rows. The batch path converts to MetricConfig
    during prefetch, before it knows each test's turn type, so it has to filter
    here instead.

    Undeclared scope means dropped, matching the ORM-level filter: a metric that
    never says which turn types it supports is not evaluated. Skipping this let
    single-turn metrics run against multi-turn conversations, where they get
    ``context=[]`` and fail by construction, inflating the metric count and
    depressing the pass rate.

    Logging follows filter_metrics_by_scope's convention: an explicitly-wrong
    scope is routine (most requirements mix Single-Turn and Multi-Turn metrics) and
    logs at debug; no declared scope at all is worth surfacing at warning, since
    the metric table's CHECK constraint makes that structurally impossible for a
    real DB row — seeing it means a non-DB caller handed in an unscoped config.
    """
    wanted = getattr(scope, "value", scope)

    kept, wrong_scope, no_scope = [], [], []
    for mc in metric_configs:
        name = getattr(mc, "name", None) or getattr(mc, "class_name", "?")
        scopes = _scope_values(mc)
        if wanted in scopes:
            kept.append(mc)
        elif scopes:
            wrong_scope.append(f"{name}({scopes})")
        else:
            no_scope.append(str(name))

    if wrong_scope:
        logger.debug(
            f"Excluded {len(wrong_scope)} metric(s) not scoped to {wanted} "
            f"for test {test_id}: {', '.join(wrong_scope)}"
        )
    if no_scope:
        logger.warning(
            f"Excluded {len(no_scope)} metric(s) with no declared metric_scope "
            f"for test {test_id}: {', '.join(no_scope)}. This metric row should "
            f"not exist — metric_scope is required and non-empty in the database."
        )

    return kept


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


def _collect_conversation_context(conversation_summary: List[Dict[str, Any]]) -> List[str]:
    """Flatten every turn's per-turn context (e.g. RAG chunks) into one list.

    context_required metrics (LLM08, ASI06, ASI08) need this at the top level of
    MetricEvaluator.evaluate(), separately from the per-turn context already
    rendered inline by ConversationHistory.format_conversation() for judges that
    read the formatted transcript directly.
    """
    context: List[str] = []
    for turn in conversation_summary:
        turn_context = turn.get(TURN_CONTEXT_KEY)
        if not turn_context:
            continue
        if isinstance(turn_context, list):
            context.extend(str(c) for c in turn_context)
        else:
            context.append(str(turn_context))
    return context


def evaluate_single_turn_metrics(
    metrics_evaluator: MetricEvaluator,
    prompt_content: str,
    expected_response: str,
    context: List[str],
    result: Dict,
    metrics: List[Union[Dict[str, Any], MetricConfig]],
    test_id: str = "unknown",
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
        test_id: Test ID, used only for the scope-filtering debug log

    Returns:
        Dictionary containing the evaluation results
    """
    metrics_results = {}

    # Extract actual_response using the fallback hierarchy
    actual_response = extract_response_with_fallback(result)
    metadata = result.get("metadata") if isinstance(result, dict) else None
    tool_calls = result.get("tool_calls") if isinstance(result, dict) else None

    # Callers normally already scope-filtered via prepare_metric_configs(...,
    # scope=MetricScope.SINGLE_TURN) before this runs (see executors/runners.py),
    # so this is defense in depth for any caller that hands in metrics directly.
    metrics = filter_configs_by_scope(metrics, MetricScope.SINGLE_TURN, test_id)

    if not metrics:
        return metrics_results

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
    from rhesis.backend.app.schemas.evaluation_contract import read_contract
    from rhesis.backend.app.services.test_interpretation import contract_usability
    from rhesis.backend.tasks.execution.executors.data import (
        get_test_metrics,
    )
    from rhesis.backend.tasks.execution.executors.metrics import (
        prepare_metric_configs,
    )

    test_config = test.test_configuration or {}
    goal = test_config.get("goal", "")
    # GoalAchievementJudge's prompt has a mandatory-instructions block a live run always
    # includes; omitting it here would let a re-score score the same conversation
    # differently from the live run that originally produced it.
    instructions = test_config.get("instructions") or ""

    # Re-scoring reuses whatever contract is currently stored -- it must not re-interpret here,
    # or two back-to-back re-scores with no intervening change could disagree for no reason.
    # Like `goal`/`instructions` two lines up, this reads the test's CURRENT definition rather
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
            return {}
        usable, reason = contract_usability(stored_contract)
        if not usable:
            logger.warning(
                "Test %s has no usable evaluation contract; discarding all multi-turn "
                "metrics rather than reporting an untrustworthy verdict: %s",
                test.id,
                reason,
            )
            _record_discard_reason(stored_output, reason)
            return {}
        contract_dict = stored_contract.model_dump(mode="json", exclude_none=True)

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
        connector_metric_sender=_build_connector_metric_sender(
            project_id, environment, organization_id
        ),
    )

    conversation_summary = stored_output.get(CONVERSATION_SUMMARY_KEY, [])
    conversation_history = _build_conversation_history(conversation_summary)

    # Use format_conversation() so that per-turn metadata, context, and tool calls
    # are rendered inline within each turn. Both single-turn judges (NumericJudge,
    # CategoricalJudge) and ConversationalJudge therefore see the same rich
    # structured transcript as their output/conversation_text input.
    conversation_text = conversation_history.format_conversation() if conversation_history else ""

    try:
        results = metrics_evaluator.evaluate(
            input_text=goal,
            output_text=conversation_text.strip(),
            expected_output="",
            context=_collect_conversation_context(conversation_summary),
            metrics=metric_configs,
            conversation_history=conversation_history,
            instructions=instructions,
            contract=contract_dict,
        )
    except Exception as e:
        logger.warning(f"Error evaluating multi-turn metrics: {str(e)}")
        results = {}

    return results
