import concurrent.futures
import dataclasses
import inspect
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.metrics.metric_service import validate_metric_configs
from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
from rhesis.sdk.metrics import BaseMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.conversational.types import ConversationHistory

logger = logging.getLogger(__name__)

# Use inline factory creation to avoid circular imports
# Implementation of the factory import will be delayed until needed

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Overall timeout for all metrics in a batch (10 minutes)
METRIC_OVERALL_TIMEOUT = 600

# Maximum number of retry attempts for transient failures
METRIC_MAX_RETRIES = 3

# Retry backoff configuration (exponential: 1s, 2s, 4s, 8s, 10s)
METRIC_RETRY_MIN_WAIT = 1  # seconds
METRIC_RETRY_MAX_WAIT = 10  # seconds


class MetricEvaluator:
    """Evaluator class that handles metric computation using configured backends."""

    # Type alias for the injected SDK metric sender.
    # Signature: (metric_run_id, metric_name, inputs) -> result dict
    SdkMetricSender = Callable[
        [str, str, Dict[str, Any]],
        Awaitable[Dict[str, Any]],
    ]

    def __init__(
        self,
        model: Optional[Any] = None,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        sdk_metric_sender: Optional["MetricEvaluator.SdkMetricSender"] = None,
    ):
        """
        Initialize evaluator with factory and score evaluator.

        Args:
            model: Optional default model for metrics evaluation.
            db: Optional database session for fetching metric-specific models.
            organization_id: Optional organization ID for secure model lookups.
            sdk_metric_sender: Optional async callable for dispatching SDK
                metrics.  Signature: (metric_run_id, metric_name, inputs)
                -> result dict.  When *None*, SDK-backend metrics are skipped.
        """
        self.score_evaluator = ScoreEvaluator()
        self.model = model
        self.db = db
        self.organization_id = organization_id
        self._sdk_metric_sender = sdk_metric_sender
        self._conversation_history: Optional[ConversationHistory] = None

    def evaluate(
        self,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        metrics: List[Union[Dict[str, Any], MetricConfig, MetricModel]],
        max_workers: int = 5,
        conversation_history: Optional[ConversationHistory] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Compute metrics using the configured backends in parallel.

        Args:
            input_text: The input query or question
            output_text: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response
            metrics: List of Metric models, MetricConfig objects, or config dictionaries, e.g.
                    [
                        # Database Metric model (direct from DB query)
                        db.query(Metric).first(),

                        # MetricConfig object
                        MetricConfig(
                            class_name="DeepEvalAnswerRelevancy",
                            backend="deepeval",
                            threshold=0.7,
                            description="Measures how relevant the answer is to the question"
                        ),

                        # Plain dictionary
                        {
                            "class_name": "DeepEvalFaithfulness",
                            "backend": "deepeval",
                            "threshold": 0.8,
                            "description": "Measures how faithful the answer is to the context"
                        }
                    ]
            max_workers: Maximum number of parallel workers for metric computation
            tool_calls: Optional list of tool calls made by the endpoint

        Returns:
            Dictionary containing scores and details for each metric
        """
        # Store conversation history, metadata, and tool_calls for metrics that accept them
        self._conversation_history = conversation_history
        self._metadata = metadata
        self._tool_calls = tool_calls

        if not metrics:
            logger.warning("No metrics provided for evaluation")
            return {}

        metric_configs, invalid_metric_results = validate_metric_configs(metrics)

        if not metric_configs:
            logger.warning("No valid metrics found after parsing")
            if invalid_metric_results:
                logger.warning(
                    f"Returning {len(invalid_metric_results)} invalid metrics as error results"
                )
                return invalid_metric_results
            else:
                logger.warning("No metrics found at all, returning empty results")
                return {}

        # Split SDK metrics from local metrics
        local_configs: List[MetricConfig] = []
        sdk_configs: List[MetricConfig] = []
        for config in metric_configs:
            backend_val = getattr(config.backend, "value", config.backend)
            if backend_val == "sdk":
                sdk_configs.append(config)
            else:
                local_configs.append(config)

        results = {}

        # Evaluate local metrics through the standard pipeline
        if local_configs:
            metric_tasks = self._prepare_metrics(local_configs, expected_output, context)
            results = self._execute_metrics_in_parallel(
                metric_tasks, input_text, output_text, expected_output, context, max_workers
            )

        # Evaluate SDK metrics via connector RPC
        if sdk_configs:
            sdk_results = self._evaluate_sdk_metrics(
                sdk_configs, input_text, output_text, expected_output, context
            )
            results.update(sdk_results)

        # Merge invalid metric results into the final results
        results.update(invalid_metric_results)

        return results

    def _evaluate_sdk_metrics(
        self,
        sdk_configs: List[MetricConfig],
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
    ) -> Dict[str, Any]:
        """
        Evaluate SDK-side metrics via the connector RPC.

        Args:
            sdk_configs: List of metric configurations with backend="sdk"
            input_text: The input query
            output_text: The actual LLM output
            expected_output: The expected output
            context: List of context strings

        Returns:
            Dictionary of metric results keyed by metric name
        """
        if not self._sdk_metric_sender:
            logger.warning("Cannot evaluate SDK metrics: no sdk_metric_sender configured")
            return {
                (c.name or f"SDKMetric_{i}"): MetricResultBuilder.error(
                    reason="SDK metric sender not configured",
                    backend="sdk",
                    name=c.name or f"SDKMetric_{i}",
                    class_name=c.class_name or "Unknown",
                    error="sdk_metric_sender not configured",
                )
                for i, c in enumerate(sdk_configs)
            }

        import asyncio
        import uuid

        results = {}

        for config in sdk_configs:
            metric_name = config.name or ""
            class_name = config.class_name or metric_name
            description = config.description or f"SDK metric: {class_name}"
            threshold = config.threshold if config.threshold is not None else 0.0

            metric_run_id = str(uuid.uuid4())

            inputs = {
                "input": input_text,
                "output": output_text,
                "expected_output": expected_output or "",
                "context": context or [],
            }

            try:
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    pass

                coro = self._sdk_metric_sender(metric_run_id, class_name, inputs)

                if loop and loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        sdk_result = pool.submit(asyncio.run, coro).result(timeout=60)
                else:
                    sdk_result = asyncio.run(coro)

                if "error" in sdk_result and "status" not in sdk_result:
                    results[metric_name or class_name] = MetricResultBuilder.error(
                        reason=sdk_result.get("details", sdk_result.get("error", "Unknown error")),
                        backend="sdk",
                        name=metric_name,
                        class_name=class_name,
                        description=description,
                        error=sdk_result.get("error"),
                        threshold=threshold,
                    )
                elif sdk_result.get("status") == "error":
                    results[metric_name or class_name] = MetricResultBuilder.error(
                        reason=sdk_result.get("error", "SDK metric error"),
                        backend="sdk",
                        name=metric_name,
                        class_name=class_name,
                        description=description,
                        error=sdk_result.get("error"),
                        threshold=threshold,
                        duration_ms=sdk_result.get("duration_ms"),
                    )
                else:
                    score = sdk_result.get("score", 0.0)
                    details = sdk_result.get("details", {})
                    threshold_op = config.threshold_operator or ">="
                    is_successful = self.score_evaluator.evaluate_score(
                        score=score,
                        threshold=threshold,
                        threshold_operator=threshold_op,
                    )

                    results[metric_name or class_name] = MetricResultBuilder.success(
                        score=score,
                        reason=details.get("reason", f"SDK metric score: {score}"),
                        is_successful=is_successful,
                        backend="sdk",
                        name=metric_name,
                        class_name=class_name,
                        description=description,
                        threshold=threshold,
                        duration_ms=sdk_result.get("duration_ms"),
                    )

            except Exception as e:
                logger.error(
                    f"Error evaluating SDK metric '{class_name}': {e}",
                    exc_info=True,
                )
                results[metric_name or class_name] = MetricResultBuilder.error(
                    reason=f"SDK metric evaluation failed: {e}",
                    backend="sdk",
                    name=metric_name,
                    class_name=class_name,
                    description=description,
                    error=str(e),
                    error_type=type(e).__name__,
                    threshold=threshold,
                )

        return results

    def _prepare_metrics(
        self,
        metrics: List[MetricConfig],
        expected_output: Optional[str],
        context: List[str] = None,
    ) -> List[Tuple[str, BaseMetric, MetricConfig, str]]:
        """
        Prepare metrics for evaluation.

        Args:
            metrics: List of metric configurations (may contain None values)
            expected_output: The expected output (to check if ground truth is required)
            context: List of context strings (to check if context is required)

        Returns:
            List of tuples containing (class_name, metric_instance, metric_config, backend)
        """

        logger.info(f"Preparing {len(metrics)} metrics for evaluation")
        metric_tasks = []

        for metric_config in metrics:
            class_name = metric_config.class_name
            backend = getattr(
                metric_config.backend, "value", metric_config.backend
            )
            threshold = metric_config.threshold
            parameters = metric_config.parameters or {}
            model_id = (metric_config.parameters or {}).get("model_id")

            try:
                # class_name and backend are already validated by diagnose_invalid_metric()
                # before configs reach this method.

                # Prepare parameters for the metric
                metric_params = {"threshold": threshold, **parameters}

                # Determine which model to use for this metric
                # Priority: metric-specific model > user's default model > system default
                metric_model = None

                # 1. Check if metric has a specific model configured
                if model_id and self.db:
                    try:
                        from rhesis.backend.app import crud
                        from rhesis.sdk.models.factory import get_model

                        # Fetch metric's preferred model from database
                        model_record = crud.get_model(
                            self.db,
                            UUID(model_id) if isinstance(model_id, str) else model_id,
                            self.organization_id,
                        )

                        if model_record and model_record.provider_type:
                            # Create BaseLLM instance for this specific metric
                            metric_model = get_model(
                                provider=model_record.provider_type.type_value,
                                model_name=model_record.model_name,
                                api_key=model_record.key,
                            )
                            metric_name_for_log = metric_config.name or class_name
                            logger.info(
                                f"[METRIC_MODEL] Using metric-specific model for "
                                f"'{metric_name_for_log}': {model_record.name} "
                                f"(provider={model_record.provider_type.type_value}, "
                                f"model={model_record.model_name})"
                            )
                        else:
                            metric_name_for_log = metric_config.name or class_name
                            logger.warning(
                                f"[METRIC_MODEL] Model ID {model_id} not found for "
                                f"metric '{metric_name_for_log}'"
                            )
                    except Exception as e:
                        metric_name_for_log = metric_config.name or class_name
                        logger.warning(
                            f"[METRIC_MODEL] Error fetching metric-specific model for "
                            f"'{metric_name_for_log}': {e}"
                        )

                # 2. Fall back to user's default evaluation model if no metric-specific model
                if metric_model is None and self.model is not None:
                    metric_model = self.model
                    metric_name_for_log = metric_config.name or class_name
                    logger.debug(
                        f"[METRIC_MODEL] Using user's default model for '{metric_name_for_log}'"
                    )

                # 3. Pass model to metric if available (will fall back to system default if None)
                if metric_model is not None:
                    metric_params["model"] = metric_model

                # Instantiate the metric directly using SDK MetricFactory
                from rhesis.sdk.metrics import MetricFactory

                metric_name = metric_config.name or class_name
                logger.debug(
                    f"[SDK_DIRECT] Creating metric directly via SDK: {metric_name or class_name}"
                )

                # Merge metric_params (which includes the model) into config dict for factory
                config_dict = dataclasses.asdict(metric_config)
                if metric_params:
                    if config_dict.get("parameters") is None:
                        config_dict["parameters"] = {}
                    config_dict["parameters"].update(metric_params)

                # Extract parameters for SDK factory
                params_dict = config_dict.get("parameters", {})

                # Flatten config: merge top-level and nested parameters
                factory_params = {**config_dict}
                factory_params.update(params_dict)

                # Remove non-parameter fields
                factory_params.pop("class_name", None)
                factory_params.pop("backend", None)
                factory_params.pop("parameters", None)

                # Create metric directly via SDK factory
                try:
                    metric = MetricFactory.create(backend, class_name, **factory_params)
                except Exception as create_error:
                    logger.error(
                        f"[SDK_DIRECT] Failed to create metric '{metric_name or class_name}' "
                        f"(class: {class_name}, backend: {backend}): {create_error}",
                        exc_info=True,
                    )
                    continue

                # Skip metrics that require ground truth if it's not provided
                if metric.requires_ground_truth and expected_output is None:
                    logger.debug(
                        f"Skipping metric '{class_name}' as it requires ground truth "
                        f"which is not provided"
                    )
                    continue

                # Add task to the list
                metric_tasks.append((class_name, metric, metric_config, backend))

            except Exception as e:
                metric_name = metric_config.name or class_name
                error_msg = (
                    f"Error preparing metric '{metric_name or class_name}' (class: '{class_name}', "
                    f"backend: '{backend}'): {str(e)}"
                )
                logger.error(error_msg, exc_info=True)

        return metric_tasks

    # ============================================================================
    # METRIC KEY GENERATION
    # ============================================================================

    def _generate_unique_metric_keys(
        self, metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]]
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Generate unique keys for each metric and initialize results dictionary.

        Args:
            metric_tasks: List of prepared metric tasks

        Returns:
            Tuple of (list of unique keys, initialized results dict)
        """
        metric_keys = []
        used_keys = set()
        results = {}

        for class_name, metric, metric_config, backend in metric_tasks:
            metric_name = metric_config.name
            base_key = metric_name if metric_name and metric_name.strip() else class_name

            # Ensure uniqueness
            unique_key = base_key
            counter = 1
            while unique_key in used_keys:
                unique_key = f"{base_key}_{counter}"
                counter += 1

            used_keys.add(unique_key)
            metric_keys.append(unique_key)
            # Pre-populate with None to track incomplete metrics
            results[unique_key] = None

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
    ) -> Dict[concurrent.futures.Future, Tuple[str, str, MetricConfig, str]]:
        """
        Submit all metric evaluation tasks to the executor.

        Args:
            executor: ThreadPoolExecutor instance
            metric_tasks: List of prepared metric tasks
            metric_keys: List of unique metric keys
            input_text: Input text for evaluation
            output_text: Output text for evaluation
            expected_output: Expected output for evaluation
            context: Context for evaluation

        Returns:
            Dictionary mapping futures to metric metadata
        """
        future_to_metric = {}

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
        """
        Collect results as metrics complete, with overall timeout.

        Args:
            future_to_metric: Mapping of futures to metric metadata
            results: Results dictionary to populate
            total_metrics: Total number of metrics
            timeout: Overall timeout in seconds

        Returns:
            Tuple of (completed_count, failed_count)
        """
        completed_count = 0
        failed_count = 0

        try:
            # Process results as they complete with overall timeout
            for future in concurrent.futures.as_completed(future_to_metric, timeout=timeout):
                unique_key, class_name, metric_config, backend = future_to_metric[future]

                try:
                    # Process the result
                    result = self._process_metric_result(future, class_name, metric_config, backend)
                    results[unique_key] = result
                    completed_count += 1
                    logger.debug(
                        f"✓ Metric '{unique_key}' completed successfully "
                        f"({completed_count}/{total_metrics})"
                    )
                except Exception as e:
                    # Ensure we always have a result, even for processing errors
                    results[unique_key] = MetricResultBuilder.error(
                        reason=f"Evaluation failed: {str(e)}",
                        backend=backend,
                        name=metric_config.name or class_name,
                        class_name=class_name,
                        description=metric_config.description
                        or f"{class_name} evaluation metric",
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
        """
        Handle metrics that didn't complete within timeout.

        Args:
            results: Results dictionary
            metric_keys: List of unique metric keys
            metric_tasks: List of prepared metric tasks

        Returns:
            Number of incomplete metrics
        """
        incomplete_metrics = [key for key, val in results.items() if val is None]

        if incomplete_metrics:
            logger.error(f"⚠ {len(incomplete_metrics)} metrics incomplete: {incomplete_metrics}")

            # Create timeout results for incomplete metrics
            for key in incomplete_metrics:
                idx = metric_keys.index(key)
                class_name, _, metric_config, backend = metric_tasks[idx]

                results[key] = MetricResultBuilder.timeout(
                    backend=backend,
                    name=metric_config.name or class_name,
                    class_name=class_name,
                    description=metric_config.description
                    or f"{class_name} evaluation metric",
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
        """
        Log a summary of the evaluation results.

        Args:
            results: Final results dictionary
        """
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
    ) -> MetricResult:
        """
        Evaluate a single metric with automatic retry on transient failures.

        Uses tenacity for intelligent retry with exponential backoff.
        Only retries on network/timeout errors, not validation errors.

        Args:
            metric: The metric instance to evaluate
            input_text: The input query or question
            output_text: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response

        Returns:
            MetricResult object with score and details

        Raises:
            Exception: After max retries exhausted
        """

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
            return self._evaluate_metric(metric, input_text, output_text, expected_output, context)

        try:
            return _execute_with_retry()
        except Exception as e:
            logger.error(
                f"Metric '{metric.name}' failed after {METRIC_MAX_RETRIES + 1} attempts: {e}",
                exc_info=True,
            )
            raise

    # ============================================================================
    # MAIN ORCHESTRATION METHOD
    # ============================================================================

    def _execute_metrics_in_parallel(
        self,
        metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]],
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        max_workers: int,
    ) -> Dict[str, Any]:
        """
        Execute metrics in parallel with overall timeout and complete accountability.

        This is the main orchestration method that coordinates metric evaluation.
        It guarantees that every metric gets a result (success, error, or timeout).

        Args:
            metric_tasks: List of prepared metric tasks
            input_text: The input query or question
            output_text: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response
            max_workers: Maximum number of parallel workers

        Returns:
            Dictionary of metric results
        """
        if not metric_tasks:
            logger.warning("No metrics to evaluate")
            return {}

        # Step 1: Generate unique keys and initialize results
        metric_keys, results = self._generate_unique_metric_keys(metric_tasks)
        total_metrics = len(metric_tasks)

        logger.info(
            f"Starting parallel evaluation of {total_metrics} metrics: {list(results.keys())}"
        )

        # Step 2: Execute metrics in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_metric = self._submit_metric_evaluations(
                executor,
                metric_tasks,
                metric_keys,
                input_text,
                output_text,
                expected_output,
                context,
            )

            # Step 3: Collect results as they complete
            completed_count, failed_count = self._collect_metric_results(
                future_to_metric,
                results,
                total_metrics,
                METRIC_OVERALL_TIMEOUT,
            )

            # Step 4: Handle incomplete metrics (timeouts)
            self._handle_incomplete_metrics(results, metric_keys, metric_tasks)

        # Step 5: Log summary
        self._log_evaluation_summary(results)

        return results

    def _call_metric_with_introspection(
        self,
        metric: BaseMetric,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
    ) -> MetricResult:
        """
        Call metric.evaluate() with only the parameters it accepts.

        Uses introspection to check the metric's signature and only passes
        parameters that are actually defined. This allows metrics to have
        different signatures (e.g., ContextualRelevancy doesn't need output).

        Args:
            metric: The metric instance to evaluate
            input_text: The input query or question
            output_text: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response

        Returns:
            MetricResult object with score and details
        """
        # Inspect the metric's evaluate signature
        sig = inspect.signature(metric.evaluate)
        params = sig.parameters

        # Build kwargs with only the parameters the metric accepts
        kwargs = {}

        # Check each potential parameter and include if present in signature
        if "input" in params:
            kwargs["input"] = input_text
        if "output" in params:
            kwargs["output"] = output_text
        if "expected_output" in params:
            kwargs["expected_output"] = expected_output
        if "context" in params:
            kwargs["context"] = context
        if "conversation_history" in params and self._conversation_history is not None:
            kwargs["conversation_history"] = self._conversation_history
        if "metadata" in params and self._metadata is not None:
            kwargs["metadata"] = self._metadata
        if "tool_calls" in params and self._tool_calls is not None:
            kwargs["tool_calls"] = self._tool_calls
        if "goal" in params:
            kwargs["goal"] = input_text

        logger.debug(f"Calling metric '{metric.name}' with parameters: {list(kwargs.keys())}")

        return metric.evaluate(**kwargs)

    def _evaluate_metric(
        self,
        metric: BaseMetric,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
    ) -> MetricResult:
        """
        Evaluate a single metric.

        Args:
            metric: The metric instance to evaluate
            input_text: The input query or question
            output_text: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response

        Returns:
            MetricResult object with score and details
        """
        logger.debug(f"Evaluating metric '{metric.name}'")
        return self._call_metric_with_introspection(
            metric, input_text, output_text, expected_output, context
        )

    def _process_metric_result(
        self,
        future: concurrent.futures.Future,
        class_name: str,
        metric_config: MetricConfig,
        backend: str,
    ) -> Dict[str, Any]:
        """
        Process the result of a metric evaluation.

        Args:
            future: The Future object containing the result
            class_name: Name of the metric class
            metric_config: Configuration for the metric
            backend: Backend used for the metric

        Returns:
            Dictionary with processed metric results
        """
        try:
            result = future.result()
            description = (
                metric_config.description or f"{class_name} evaluation metric"
            )

            if "is_successful" in result.details and result.details["is_successful"] is not None:
                is_successful = result.details["is_successful"]
                logger.debug(
                    f"Using metric's own is_successful value for '{class_name}': {is_successful}"
                )
            else:
                is_successful = self.score_evaluator.evaluate_score(
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

            threshold = metric_config.threshold
            reference_score = metric_config.reference_score
            logger.debug(f"Completed metric '{class_name}' with score {result.score}")
            return MetricResultBuilder.success(
                score=result.score,
                reason=result.details.get("reason", f"Score: {result.score}"),
                is_successful=is_successful,
                backend=backend,
                name=metric_config.name or class_name,
                class_name=class_name,
                description=description,
                threshold=threshold,
                reference_score=reference_score,
            )

        except Exception as exc:
            import traceback

            logger.error(f"Metric '{class_name}' generated an exception: {exc}", exc_info=True)
            logger.error(f"Backend: {backend}")
            logger.error(f"Metric config: {metric_config}")
            logger.error(f"Exception type: {type(exc).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            error_description = (
                metric_config.description or f"{class_name} evaluation metric"
            )
            threshold = metric_config.threshold
            reference_score = metric_config.reference_score
            return MetricResultBuilder.error(
                reason=f"Error: {str(exc)}",
                backend=backend,
                name=metric_config.name or class_name,
                class_name=class_name,
                description=error_description,
                error=str(exc),
                error_type=type(exc).__name__,
                threshold=threshold,
                reference_score=reference_score,
            )
