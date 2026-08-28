"""
Local strategy for metric evaluation.

Handles all metrics that run locally (rhesis, deepeval, etc.) via the SDK
MetricFactory.  Owns the parallel execution pipeline that was previously
part of MetricEvaluator.
"""

import asyncio
import concurrent.futures
import dataclasses
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rhesis.backend.app.usage_attribution import with_usage_attribution
from rhesis.backend.metrics.metric_config import build_metric_evaluate_params
from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
from rhesis.backend.metrics.strategies.base import OnMetricComplete
from rhesis.sdk.metrics import BaseMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.conversational.types import ConversationHistory

logger = logging.getLogger(__name__)

# Overall timeout for all metrics in a batch (10 minutes)
METRIC_OVERALL_TIMEOUT = 600

# Maximum number of retry attempts for transient failures
METRIC_MAX_RETRIES = 3

# Retry backoff configuration (exponential: 1s, 2s, 4s, 8s, 10s)
METRIC_RETRY_MIN_WAIT = 1
METRIC_RETRY_MAX_WAIT = 10

# GoalAchievementJudge detail fields worth surfacing alongside score/reason/is_successful.
# Without this, MetricResultBuilder's fixed field list drops them, so a re-scored run loses
# the per-item breakdown that the live run displayed.
#
# Note this does NOT fix the "0/0 criteria" display on a re-scored *legacy* goal-based run.
# The count fields the metrics card reads for those (`criteria_met`/`criteria_total`) are
# derived by Penelope in `context.py:_flatten_metric_result`, not returned by the SDK judge,
# so they are never present in `result.details` and cannot be copied here. Only the
# contract-based keys below (`behaviors_*`) carry their own counts and therefore survive a
# re-score.
#
# Deliberately NOT `**result.details`: `_get_base_details(prompt)` puts the entire rendered
# evaluation prompt in `details["prompt"]`, and that must not be echoed into stored
# test_metrics (size, and it discloses internal prompt text). Metric-agnostic on purpose --
# it simply copies whichever of these keys a result happens to carry, so it costs nothing
# for metrics that don't have them.
_GOAL_ACHIEVEMENT_EXTRA_KEYS = (
    # Legacy goal-based scoring (GoalAchievementScoreResponse)
    "criteria_evaluations",
    "all_criteria_met",
    "confidence",
    "turn_count",
    # Contract-based scoring (ContractComplianceResponse / _a_evaluate_contract)
    "behavior_verdicts",
    "behaviors_total",
    "behaviors_complied",
    "behaviors_violated",
    "violated_behaviors",
    "adversarial",
    "contract",
)


def _extract_goal_achievement_extra(details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Curated, size-bounded subset of a result's details worth storing alongside it."""
    extra = {key: details[key] for key in _GOAL_ACHIEVEMENT_EXTRA_KEYS if key in details}
    return extra or None


class LocalStrategy:
    """Evaluates metrics locally via the SDK MetricFactory.

    Handles all non-sdk backends (rhesis, deepeval, etc.) by instantiating
    metric objects through MetricFactory and running them in a thread pool.
    Acts as the default/fallback strategy in MetricEvaluator.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        score_evaluator: Optional[ScoreEvaluator] = None,
        metric_models: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._model = model
        self._db = db
        self._organization_id = organization_id
        self._score_evaluator = score_evaluator or ScoreEvaluator()
        self._metric_models = metric_models

    def backend_value(self) -> str:
        return "__local__"

    def evaluate(
        self,
        configs: List[MetricConfig],
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        *,
        max_workers: int = 5,
        conversation_history: Any = None,
        metadata: Dict[str, Any] | None = None,
        tool_calls: List[Dict[str, Any]] | None = None,
        instructions: str | None = None,
        contract: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Evaluate all local strategy configs in parallel."""
        metric_tasks = prepare_metrics(
            configs,
            expected_output,
            context,
            model=self._model,
            db=self._db,
            organization_id=self._organization_id,
            metric_models=self._metric_models,
        )
        return self._execute_metrics_in_parallel(
            metric_tasks,
            input_text,
            output_text,
            expected_output,
            context,
            max_workers,
            conversation_history=conversation_history,
            metadata=metadata,
            tool_calls=tool_calls,
            instructions=instructions,
            contract=contract,
        )

    async def a_evaluate(
        self,
        configs: List[MetricConfig],
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        *,
        max_workers: int = 5,
        conversation_history: Any = None,
        metadata: Dict[str, Any] | None = None,
        tool_calls: List[Dict[str, Any]] | None = None,
        instructions: str | None = None,
        contract: Dict[str, Any] | None = None,
        on_metric_complete: OnMetricComplete = None,
    ) -> Dict[str, Any]:
        """Async evaluate using asyncio.gather over metric.a_evaluate().

        Mirrors the sync path's resilience: bounded concurrency via semaphore,
        per-metric retry for transient failures, and an overall timeout.
        """
        metric_tasks = prepare_metrics(
            configs,
            expected_output,
            context,
            model=self._model,
            db=self._db,
            organization_id=self._organization_id,
            metric_models=self._metric_models,
        )
        if not metric_tasks:
            logger.warning("No metrics to evaluate (async)")
            return {}

        metric_keys, results = self._generate_unique_metric_keys(metric_tasks)
        sem = asyncio.Semaphore(max_workers)

        async def _eval_one(
            unique_key: str,
            class_name: str,
            metric: BaseMetric,
            metric_config: MetricConfig,
            backend: str,
        ) -> Tuple[str, Dict[str, Any]]:
            async with sem:
                key, result = await self._a_eval_one_with_retry(
                    unique_key,
                    class_name,
                    metric,
                    metric_config,
                    backend,
                    input_text,
                    output_text,
                    expected_output,
                    context,
                    conversation_history=conversation_history,
                    metadata=metadata,
                    tool_calls=tool_calls,
                    instructions=instructions,
                    contract=contract,
                )
                if on_metric_complete:
                    try:
                        on_metric_complete(key, result)
                    except Exception:
                        pass
                return key, result

        coros = [
            _eval_one(key, cn, m, mc, b)
            for (cn, m, mc, b), key in zip(metric_tasks, metric_keys, strict=True)
        ]

        try:
            eval_results = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                timeout=METRIC_OVERALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(f"Overall async metric timeout ({METRIC_OVERALL_TIMEOUT}s) reached")
            eval_results = []

        for item in eval_results:
            if isinstance(item, Exception):
                logger.error(f"Unexpected gather exception: {item}")
                continue
            key, val = item
            results[key] = val

        self._handle_incomplete_metrics(results, metric_keys, metric_tasks)
        self._log_evaluation_summary(results)
        return results

    async def _a_eval_one_with_retry(
        self,
        unique_key: str,
        class_name: str,
        metric: BaseMetric,
        metric_config: MetricConfig,
        backend: str,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        *,
        conversation_history: Any = None,
        metadata: Dict[str, Any] | None = None,
        tool_calls: List[Dict[str, Any]] | None = None,
        instructions: str | None = None,
        contract: Dict[str, Any] | None = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Evaluate a single metric with retry for transient errors."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, METRIC_MAX_RETRIES + 2):
            try:
                kwargs = build_metric_evaluate_params(
                    metric,
                    input_text,
                    output_text,
                    expected_output,
                    context,
                    conversation_history=conversation_history,
                    metadata=metadata,
                    tool_calls=tool_calls,
                    instructions=instructions,
                    contract=contract,
                )
                result = await metric.a_evaluate(**kwargs)
                description = metric_config.description or f"{class_name} evaluation metric"

                if result.details.get("inconclusive"):
                    is_successful = None
                elif (
                    "is_successful" in result.details
                    and result.details["is_successful"] is not None
                ):
                    is_successful = result.details["is_successful"]
                else:
                    is_successful = self._score_evaluator.evaluate_score(
                        score=result.score,
                        threshold=metric_config.threshold,
                        threshold_operator=metric_config.threshold_operator,
                        reference_score=metric_config.reference_score,
                        categories=metric_config.categories,
                        passing_categories=metric_config.passing_categories,
                    )

                return unique_key, MetricResultBuilder.success(
                    score=result.score,
                    reason=result.details.get("reason", f"Score: {result.score}"),
                    is_successful=is_successful,
                    backend=backend,
                    name=metric_config.name or class_name,
                    class_name=class_name,
                    description=description,
                    threshold=metric_config.threshold,
                    reference_score=metric_config.reference_score,
                    extra=_extract_goal_achievement_extra(result.details),
                )
            except (TimeoutError, ConnectionError, OSError) as e:
                last_exc = e
                if attempt <= METRIC_MAX_RETRIES:
                    wait = min(
                        METRIC_RETRY_MAX_WAIT,
                        METRIC_RETRY_MIN_WAIT * (2 ** (attempt - 1)),
                    )
                    logger.warning(
                        f"Async metric '{class_name}' transient error "
                        f"(attempt {attempt}/{METRIC_MAX_RETRIES + 1}), "
                        f"retrying in {wait}s: {e}"
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(
                    f"Async metric '{class_name}' failed after "
                    f"{METRIC_MAX_RETRIES + 1} attempts: {e}",
                    exc_info=True,
                )
            except Exception as e:
                last_exc = e
                logger.error(f"Async metric '{class_name}' failed: {e}", exc_info=True)
                break

        return unique_key, MetricResultBuilder.error(
            reason=f"Evaluation failed: {str(last_exc)}",
            backend=backend,
            name=metric_config.name or class_name,
            class_name=class_name,
            description=(metric_config.description or f"{class_name} evaluation metric"),
            error=str(last_exc),
            error_type=type(last_exc).__name__,
            threshold=(metric_config.threshold if metric_config.threshold is not None else 0.0),
        )

    # ============================================================================
    # METRIC KEY GENERATION
    # ============================================================================

    def _generate_unique_metric_keys(
        self, metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]]
    ) -> Tuple[List[str], Dict[str, Any]]:
        # Suffixes are assigned in a stable order (name, class_name, id) rather
        # than the caller's iteration order, which is not guaranteed stable
        # across runs. Otherwise two duplicate-named metrics could swap which
        # one gets the bare key and which gets "_1" from one run to the next,
        # breaking the verdict matrix's assumption that a metric key identifies
        # the same metric across the run's lifetime.
        def _stable_sort_key(index: int) -> Tuple[str, str, str]:
            _, _, metric_config, _ = metric_tasks[index]
            return (
                metric_config.name or "",
                metric_config.class_name or "",
                str(metric_config.id or ""),
            )

        order = sorted(range(len(metric_tasks)), key=_stable_sort_key)

        used_keys: set = set()
        assigned: Dict[int, str] = {}
        for index in order:
            class_name, metric, metric_config, backend = metric_tasks[index]
            metric_name = metric_config.name
            base_key = metric_name if metric_name and metric_name.strip() else class_name

            unique_key = base_key
            counter = 1
            while unique_key in used_keys:
                unique_key = f"{base_key}_{counter}"
                counter += 1

            used_keys.add(unique_key)
            assigned[index] = unique_key

        metric_keys = [assigned[index] for index in range(len(metric_tasks))]
        results: Dict[str, Any] = {key: None for key in metric_keys}

        return metric_keys, results

    # ============================================================================
    # METRIC SUBMISSION
    # ============================================================================

    def _submit_metric_evaluations(
        self,
        executor: concurrent.futures.ThreadPoolExecutor,
        metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]],
        metric_keys: List[str],
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        *,
        conversation_history: Optional[ConversationHistory] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        instructions: str | None = None,
        contract: Dict[str, Any] | None = None,
    ) -> Dict[concurrent.futures.Future, Tuple[str, str, MetricConfig, str]]:
        future_to_metric: Dict[concurrent.futures.Future, Tuple[str, str, MetricConfig, str]] = {}

        for (class_name, metric, metric_config, backend), unique_key in zip(
            metric_tasks, metric_keys, strict=True
        ):
            # ThreadPoolExecutor does not carry contextvars into its workers
            # the way asyncio.to_thread does, and an LLM judge running here
            # emits token usage that has to name an org. Without this the
            # judge's tokens land in the unattributed bucket.
            future = executor.submit(
                with_usage_attribution(self._evaluate_metric_with_retry),
                metric,
                input_text,
                output_text,
                expected_output,
                context,
                conversation_history=conversation_history,
                metadata=metadata,
                tool_calls=tool_calls,
                instructions=instructions,
                contract=contract,
            )
            future_to_metric[future] = (unique_key, class_name, metric_config, backend)

        return future_to_metric

    # ============================================================================
    # RESULT COLLECTION
    # ============================================================================

    def _collect_metric_results(
        self,
        future_to_metric: Dict[concurrent.futures.Future, Tuple[str, str, MetricConfig, str]],
        results: Dict[str, Any],
        total_metrics: int,
        timeout: int,
    ) -> Tuple[int, int]:
        completed_count = 0
        failed_count = 0

        try:
            for future in concurrent.futures.as_completed(future_to_metric, timeout=timeout):
                unique_key, class_name, metric_config, backend = future_to_metric[future]

                try:
                    result = self._process_metric_result(future, class_name, metric_config, backend)
                    results[unique_key] = result
                    completed_count += 1
                    logger.debug(
                        f"✓ Metric '{unique_key}' completed successfully "
                        f"({completed_count}/{total_metrics})"
                    )
                except Exception as e:
                    results[unique_key] = MetricResultBuilder.error(
                        reason=f"Evaluation failed: {str(e)}",
                        backend=backend,
                        name=metric_config.name or class_name,
                        class_name=class_name,
                        description=metric_config.description or f"{class_name} evaluation metric",
                        error=str(e),
                        error_type=type(e).__name__,
                        threshold=metric_config.threshold
                        if metric_config.threshold is not None
                        else 0.0,
                    )
                    failed_count += 1
                    completed_count += 1
                    logger.error(
                        f"✗ Metric '{unique_key}' failed ({completed_count}/{total_metrics}): {e}"
                    )

        except concurrent.futures.TimeoutError:
            logger.error(
                f"⏱ Overall timeout ({timeout}s) reached. "
                f"{completed_count}/{total_metrics} metrics completed"
            )
        except Exception as e:
            logger.error(f"Unexpected error in result collection: {e}", exc_info=True)

        return completed_count, failed_count

    # ============================================================================
    # INCOMPLETE METRIC HANDLING
    # ============================================================================

    def _handle_incomplete_metrics(
        self,
        results: Dict[str, Any],
        metric_keys: List[str],
        metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]],
    ) -> int:
        incomplete_metrics = [key for key, val in results.items() if val is None]

        if incomplete_metrics:
            logger.error(f"⚠ {len(incomplete_metrics)} metrics incomplete: {incomplete_metrics}")

            # Build O(1) lookup once rather than calling list.index() (O(n)) per key.
            key_to_task = {key: metric_tasks[i] for i, key in enumerate(metric_keys)}

            for key in incomplete_metrics:
                class_name, _, metric_config, backend = key_to_task[key]

                results[key] = MetricResultBuilder.timeout(
                    backend=backend,
                    name=metric_config.name or class_name,
                    class_name=class_name,
                    description=metric_config.description or f"{class_name} evaluation metric",
                    threshold=metric_config.threshold
                    if metric_config.threshold is not None
                    else 0.0,
                    timeout_seconds=METRIC_OVERALL_TIMEOUT,
                )

        return len(incomplete_metrics)

    # ============================================================================
    # SUMMARY LOGGING
    # ============================================================================

    def _log_evaluation_summary(self, results: Dict[str, Any]) -> None:
        successful = sum(1 for r in results.values() if r and r.get("is_successful", False))
        failed = sum(1 for r in results.values() if r and not r.get("is_successful", False))
        logger.info(
            f"📊 Metric evaluation complete: {successful} successful, "
            f"{failed} failed/timed out (total: {len(results)})"
        )

    # ============================================================================
    # RETRY WRAPPER
    # ============================================================================

    def _evaluate_metric_with_retry(
        self,
        metric: BaseMetric,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        *,
        conversation_history: Optional[ConversationHistory] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        instructions: str | None = None,
        contract: Dict[str, Any] | None = None,
    ) -> MetricResult:
        @retry(
            retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
            stop=stop_after_attempt(METRIC_MAX_RETRIES + 1),
            wait=wait_exponential(
                multiplier=1, min=METRIC_RETRY_MIN_WAIT, max=METRIC_RETRY_MAX_WAIT
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _execute_with_retry():
            return self._evaluate_metric(
                metric,
                input_text,
                output_text,
                expected_output,
                context,
                conversation_history=conversation_history,
                metadata=metadata,
                tool_calls=tool_calls,
                instructions=instructions,
                contract=contract,
            )

        try:
            return _execute_with_retry()
        except Exception as e:
            logger.error(
                f"Metric '{metric.name}' failed after {METRIC_MAX_RETRIES + 1} attempts: {e}",
                exc_info=True,
            )
            raise

    # ============================================================================
    # SINGLE METRIC EVALUATION
    # ============================================================================

    def _evaluate_metric(
        self,
        metric: BaseMetric,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        *,
        conversation_history: Optional[ConversationHistory] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        instructions: str | None = None,
        contract: Dict[str, Any] | None = None,
    ) -> MetricResult:
        logger.debug(f"Evaluating metric '{metric.name}'")
        kwargs = build_metric_evaluate_params(
            metric,
            input_text,
            output_text,
            expected_output,
            context,
            conversation_history=conversation_history,
            metadata=metadata,
            tool_calls=tool_calls,
            instructions=instructions,
            contract=contract,
        )
        logger.debug(f"Calling metric '{metric.name}' with parameters: {list(kwargs.keys())}")
        return metric.evaluate(**kwargs)

    def _process_metric_result(
        self,
        future: concurrent.futures.Future,
        class_name: str,
        metric_config: MetricConfig,
        backend: str,
    ) -> Dict[str, Any]:
        try:
            result = future.result()
            description = metric_config.description or f"{class_name} evaluation metric"

            if result.details.get("inconclusive"):
                is_successful = None
                logger.debug(f"Metric '{class_name}' returned inconclusive result (no score)")
            elif "is_successful" in result.details and result.details["is_successful"] is not None:
                is_successful = result.details["is_successful"]
                logger.debug(
                    f"Using metric's own is_successful value for '{class_name}': {is_successful}"
                )
            else:
                is_successful = self._score_evaluator.evaluate_score(
                    score=result.score,
                    threshold=metric_config.threshold,
                    threshold_operator=metric_config.threshold_operator,
                    reference_score=metric_config.reference_score,
                    categories=metric_config.categories,
                    passing_categories=metric_config.passing_categories,
                )
                logger.debug(
                    f"Computed is_successful for '{class_name}' using score evaluator: "
                    f"{is_successful}"
                )

            logger.debug(f"Completed metric '{class_name}' with score {result.score}")
            return MetricResultBuilder.success(
                score=result.score,
                reason=result.details.get("reason", f"Score: {result.score}"),
                is_successful=is_successful,
                backend=backend,
                name=metric_config.name or class_name,
                class_name=class_name,
                description=description,
                threshold=metric_config.threshold,
                reference_score=metric_config.reference_score,
                extra=_extract_goal_achievement_extra(result.details),
            )

        except Exception as exc:
            import traceback

            logger.error(f"Metric '{class_name}' generated an exception: {exc}", exc_info=True)
            logger.error(f"Backend: {backend}")
            logger.error(f"Metric config: {metric_config}")
            logger.error(f"Exception type: {type(exc).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            return MetricResultBuilder.error(
                reason=f"Error: {str(exc)}",
                backend=backend,
                name=metric_config.name or class_name,
                class_name=class_name,
                description=metric_config.description or f"{class_name} evaluation metric",
                error=str(exc),
                error_type=type(exc).__name__,
                threshold=metric_config.threshold,
                reference_score=metric_config.reference_score,
            )

    # ============================================================================
    # MAIN ORCHESTRATION
    # ============================================================================

    def _execute_metrics_in_parallel(
        self,
        metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]],
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        max_workers: int,
        *,
        conversation_history: Optional[ConversationHistory] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        instructions: str | None = None,
        contract: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if not metric_tasks:
            logger.warning("No metrics to evaluate")
            return {}

        metric_keys, results = self._generate_unique_metric_keys(metric_tasks)
        total_metrics = len(metric_tasks)

        logger.info(
            f"Starting parallel evaluation of {total_metrics} metrics: {list(results.keys())}"
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_metric = self._submit_metric_evaluations(
                executor,
                metric_tasks,
                metric_keys,
                input_text,
                output_text,
                expected_output,
                context,
                conversation_history=conversation_history,
                metadata=metadata,
                tool_calls=tool_calls,
                instructions=instructions,
                contract=contract,
            )

            self._collect_metric_results(
                future_to_metric,
                results,
                total_metrics,
                METRIC_OVERALL_TIMEOUT,
            )

            self._handle_incomplete_metrics(results, metric_keys, metric_tasks)

        self._log_evaluation_summary(results)

        return results


# ============================================================================
# MODULE-LEVEL HELPERS (metric preparation pipeline)
# ============================================================================


def _resolve_metric_model(
    model_id: str,
    db: Session,
    organization_id: Optional[str],
    metric_name_for_log: str,
) -> Optional[Any]:
    """Fetch a metric-specific LLM model from the database and instantiate it."""
    try:
        from rhesis.backend.app.crud import model as model_crud
        from rhesis.sdk.models.factory import get_model

        model_record = model_crud.get_model(
            db,
            UUID(model_id) if isinstance(model_id, str) else model_id,
            organization_id,
        )

        if model_record and model_record.provider_type:
            from rhesis.backend.app.utils.usage_tracking import stamp_usage_provenance
            from rhesis.backend.app.utils.user_model_utils import (
                _is_hosted_model,
                has_own_credentials,
            )

            provider = model_record.provider_type.type_value
            # Same normalization as _fetch_and_configure_model: a whitespace-only
            # key must not reach the provider as a real one.
            api_key = (model_record.key or "").strip() or None

            if not has_own_credentials(provider, api_key, model_record.endpoint):
                # Would fall back to this deployment's environment credentials.
                # Returning None drops to the default judge, which is a better
                # outcome than silently evaluating on our own account.
                logger.warning(
                    f"[METRIC_MODEL] Model {model_id} for metric '{metric_name_for_log}' has "
                    f"neither an API key nor an endpoint; using the default judge instead of "
                    f"running it on this deployment's credentials"
                )
                return None

            extra_params = {}
            if model_record.endpoint and model_record.endpoint.strip():
                extra_params["api_base"] = model_record.endpoint.strip()
            llm = stamp_usage_provenance(
                get_model(
                    provider=provider,
                    model_name=model_record.model_name,
                    api_key=api_key,
                    **extra_params,
                ),
                metered=_is_hosted_model(provider, api_key),
            )
            logger.info(
                f"[METRIC_MODEL] Using metric-specific model for "
                f"'{metric_name_for_log}': {model_record.name} "
                f"(provider={model_record.provider_type.type_value}, "
                f"model={model_record.model_name})"
            )
            return llm

        logger.warning(
            f"[METRIC_MODEL] Model ID {model_id} not found for metric '{metric_name_for_log}'"
        )
    except Exception as e:
        logger.warning(
            f"[METRIC_MODEL] Error fetching metric-specific model for '{metric_name_for_log}': {e}"
        )
    return None


def _select_metric_model(
    model_id: str,
    db: Optional[Session],
    organization_id: Optional[str],
    metric_name_for_log: str,
    metric_models: Optional[Dict[str, Any]],
) -> Optional[Any]:
    """Pick the judge model for a metric that configured its own `model_id`.

    Prefers a pre-resolved model over the session, because the batch path runs
    after its session is closed and can only resolve while it is still open.
    Returning None here means the caller falls back to the default judge, so
    every path that cannot honour the override says so at warning level -- a
    silently ignored override is indistinguishable from having configured none.
    """
    if metric_models is not None and model_id in metric_models:
        pre_resolved = metric_models[model_id]
        if pre_resolved is None:
            logger.warning(
                f"[METRIC_MODEL] Model {model_id} configured for metric "
                f"'{metric_name_for_log}' could not be resolved; using the default judge"
            )
        return pre_resolved

    if db is not None:
        return _resolve_metric_model(model_id, db, organization_id, metric_name_for_log)

    logger.warning(
        f"[METRIC_MODEL] Metric '{metric_name_for_log}' configures model {model_id} but it was "
        f"neither pre-resolved nor resolvable here (no database session); using the default judge"
    )
    return None


def prepare_metrics(
    metrics: List[MetricConfig],
    expected_output: Optional[str],
    context: Optional[List[str]] = None,
    model: Optional[Any] = None,
    db: Optional[Session] = None,
    organization_id: Optional[str] = None,
    metric_models: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, BaseMetric, MetricConfig, str]]:
    """Instantiate metric objects via SDK factory, resolving models from DB.

    Args:
        metrics: List of metric configurations (may contain None values).
        expected_output: The expected output (to check if ground truth is required).
        context: List of context strings (to check if context is required).
        model: Optional default LLM model for metrics evaluation.
        db: Optional database session for fetching metric-specific models.
        organization_id: Optional organization ID for secure model lookups.
        metric_models: Models already resolved by `model_id` for callers with no live
            session (the batch path). Key present with a value means resolved; key
            present with `None` means resolution was attempted and failed; key absent
            means not attempted, so fall back to resolving against `db`.

    Returns:
        List of tuples containing (class_name, metric_instance, metric_config, backend).
    """
    logger.info(f"Preparing {len(metrics)} metrics for evaluation")
    metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]] = []

    for metric_config in metrics:
        class_name = metric_config.class_name
        backend = getattr(metric_config.backend, "value", metric_config.backend)
        threshold = metric_config.threshold
        parameters = metric_config.parameters or {}
        model_id = parameters.get("model_id")

        try:
            metric_params: Dict[str, Any] = {"threshold": threshold, **parameters}
            metric_name_for_log = metric_config.name or class_name

            metric_model = None

            if model_id:
                metric_model = _select_metric_model(
                    model_id, db, organization_id, metric_name_for_log, metric_models
                )

            if metric_model is None and model is not None:
                metric_model = model
                logger.debug(
                    f"[METRIC_MODEL] Using user's default model for '{metric_name_for_log}'"
                )

            if metric_model is not None:
                metric_params["model"] = metric_model

            from rhesis.sdk.metrics import MetricFactory

            metric_name = metric_config.name or class_name
            logger.debug(
                f"[SDK_DIRECT] Creating metric directly via SDK: {metric_name or class_name}"
            )

            config_dict = dataclasses.asdict(metric_config)
            if metric_params:
                if config_dict.get("parameters") is None:
                    config_dict["parameters"] = {}
                config_dict["parameters"].update(metric_params)

            params_dict = config_dict.get("parameters", {})
            factory_params = {**config_dict}
            factory_params.update(params_dict)

            factory_params.pop("class_name", None)
            factory_params.pop("backend", None)
            factory_params.pop("parameters", None)

            try:
                metric = MetricFactory.create(backend, class_name, **factory_params)
            except Exception as create_error:
                logger.error(
                    f"[SDK_DIRECT] Failed to create metric "
                    f"'{metric_name or class_name}' "
                    f"(class: {class_name}, backend: {backend}): "
                    f"{create_error}",
                    exc_info=True,
                )
                continue

            if metric.requires_ground_truth and expected_output is None:
                logger.debug(
                    f"Skipping metric '{class_name}' as it requires "
                    f"ground truth which is not provided"
                )
                continue

            metric_tasks.append((class_name, metric, metric_config, backend))

        except Exception as e:
            metric_name = metric_config.name or class_name
            error_msg = (
                f"Error preparing metric '{metric_name or class_name}' "
                f"(class: '{class_name}', backend: '{backend}'): {str(e)}"
            )
            logger.error(error_msg, exc_info=True)

    return metric_tasks
