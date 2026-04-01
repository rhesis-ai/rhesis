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

from rhesis.backend.metrics.metric_config import build_metric_evaluate_params
from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
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
    ) -> None:
        self._model = model
        self._db = db
        self._organization_id = organization_id
        self._score_evaluator = score_evaluator or ScoreEvaluator()

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
    ) -> Dict[str, Any]:
        """Evaluate all local strategy configs in parallel."""
        metric_tasks = prepare_metrics(
            configs,
            expected_output,
            context,
            model=self._model,
            db=self._db,
            organization_id=self._organization_id,
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
                return await self._a_eval_one_with_retry(
                    unique_key, class_name, metric, metric_config, backend,
                    input_text, output_text, expected_output, context,
                    conversation_history=conversation_history,
                    metadata=metadata,
                    tool_calls=tool_calls,
                )

        coros = [
            _eval_one(key, cn, m, mc, b)
            for (cn, m, mc, b), key in zip(metric_tasks, metric_keys)
        ]

        try:
            eval_results = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                timeout=METRIC_OVERALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Overall async metric timeout ({METRIC_OVERALL_TIMEOUT}s) reached"
            )
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
                )
                result = await metric.a_evaluate(**kwargs)
                description = (
                    metric_config.description or f"{class_name} evaluation metric"
                )

                if (
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
                logger.error(
                    f"Async metric '{class_name}' failed: {e}", exc_info=True
                )
                break

        return unique_key, MetricResultBuilder.error(
            reason=f"Evaluation failed: {str(last_exc)}",
            backend=backend,
            name=metric_config.name or class_name,
            class_name=class_name,
            description=(
                metric_config.description or f"{class_name} evaluation metric"
            ),
            error=str(last_exc),
            error_type=type(last_exc).__name__,
            threshold=(
                metric_config.threshold
                if metric_config.threshold is not None
                else 0.0
            ),
        )

    # ============================================================================
    # METRIC KEY GENERATION
    # ============================================================================

    def _generate_unique_metric_keys(
        self, metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]]
    ) -> Tuple[List[str], Dict[str, Any]]:
        metric_keys = []
        used_keys: set = set()
        results: Dict[str, Any] = {}

        for class_name, metric, metric_config, backend in metric_tasks:
            metric_name = metric_config.name
            base_key = metric_name if metric_name and metric_name.strip() else class_name

            unique_key = base_key
            counter = 1
            while unique_key in used_keys:
                unique_key = f"{base_key}_{counter}"
                counter += 1

            used_keys.add(unique_key)
            metric_keys.append(unique_key)
            results[unique_key] = None  # pre-populate to track incomplete metrics

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
    ) -> Dict[concurrent.futures.Future, Tuple[str, str, MetricConfig, str]]:
        future_to_metric: Dict[concurrent.futures.Future, Tuple[str, str, MetricConfig, str]] = {}

        for (class_name, metric, metric_config, backend), unique_key in zip(
            metric_tasks, metric_keys
        ):
            future = executor.submit(
                self._evaluate_metric_with_retry,
                metric,
                input_text,
                output_text,
                expected_output,
                context,
                conversation_history=conversation_history,
                metadata=metadata,
                tool_calls=tool_calls,
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

            if "is_successful" in result.details and result.details["is_successful"] is not None:
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
        from rhesis.backend.app import crud
        from rhesis.sdk.models.factory import get_model

        model_record = crud.get_model(
            db,
            UUID(model_id) if isinstance(model_id, str) else model_id,
            organization_id,
        )

        if model_record and model_record.provider_type:
            llm = get_model(
                provider=model_record.provider_type.type_value,
                model_name=model_record.model_name,
                api_key=model_record.key,
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


def prepare_metrics(
    metrics: List[MetricConfig],
    expected_output: Optional[str],
    context: Optional[List[str]] = None,
    model: Optional[Any] = None,
    db: Optional[Session] = None,
    organization_id: Optional[str] = None,
) -> List[Tuple[str, BaseMetric, MetricConfig, str]]:
    """Instantiate metric objects via SDK factory, resolving models from DB.

    Args:
        metrics: List of metric configurations (may contain None values).
        expected_output: The expected output (to check if ground truth is required).
        context: List of context strings (to check if context is required).
        model: Optional default LLM model for metrics evaluation.
        db: Optional database session for fetching metric-specific models.
        organization_id: Optional organization ID for secure model lookups.

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

            if model_id and db:
                metric_model = _resolve_metric_model(
                    model_id, db, organization_id, metric_name_for_log
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
