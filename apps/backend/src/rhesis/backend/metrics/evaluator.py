import concurrent.futures
import inspect
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.sdk.metrics import BaseMetric, MetricConfig, MetricResult
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
from rhesis.backend.metrics.utils import diagnose_invalid_metric

# Use inline factory creation to avoid circular imports
# Implementation of the factory import will be delayed until needed


class MetricEvaluator:
    """Evaluator class that handles metric computation using configured backends."""

    def __init__(
        self,
        model: Optional[Any] = None,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
    ):
        """
        Initialize evaluator with factory and score evaluator.

        Args:
            model: Optional default model for metrics evaluation. Can be:
                   - None: Use default model from constants
                   - str: Provider name (e.g., "gemini", "openai")
                   - BaseLLM instance: Fully configured model
            db: Optional database session for fetching metric-specific models
            organization_id: Optional organization ID for secure model lookups
        """
        self.score_evaluator = ScoreEvaluator()
        self.model = model  # Store default model for passing to metrics
        self.db = db  # Database session for fetching metric-specific models
        self.organization_id = organization_id  # For secure model lookups

    @staticmethod
    def _get_config_value(config: Union[Dict, MetricConfig], key: str, default: Any = None) -> Any:
        """Helper to get a value from either dict or MetricConfig object."""
        if isinstance(config, dict):
            return config.get(key, default)
        return getattr(config, key, default)

    def evaluate(
        self,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        metrics: List[Union[Dict[str, Any], MetricConfig]],
        max_workers: int = 5,
    ) -> Dict[str, Any]:
        """
        Compute metrics using the configured backends in parallel.

        Args:
            input_text: The input query or question
            output_text: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response
            metrics: List of MetricConfig objects or config dictionaries, e.g.
                    [
                        MetricConfig(
                            class_name="DeepEvalAnswerRelevancy",
                            backend="deepeval",
                            threshold=0.7,
                            description="Measures how relevant the answer is to the question"
                        ),
                        # Or plain dictionaries
                        {
                            "class_name": "DeepEvalFaithfulness",
                            "backend": "deepeval",
                            "threshold": 0.8,
                            "description": "Measures how faithful the answer is to the context"
                        }
                    ]
            max_workers: Maximum number of parallel workers for metric computation

        Returns:
            Dictionary containing scores and details for each metric
        """
        logger.debug(f"🔍 [DEBUG EVALUATOR] evaluate() called with {len(metrics) if metrics else 0} metrics")
        if not metrics:
            logger.warning("No metrics provided for evaluation")
            return {}

        logger.debug(f"🔍 [DEBUG EVALUATOR] Starting metric processing...")
        # Convert any dict configs to MetricConfig objects, keeping track of invalid ones
        metric_configs = []
        invalid_metric_results = {}  # Store results for invalid metrics

        for i, config in enumerate(metrics):
            logger.debug(f"🔍 [DEBUG EVALUATOR] Processing metric {i}: type={type(config)}")
            # Accept both MetricConfig objects and dicts - adapter handles both
            if isinstance(config, (MetricConfig, dict)):
                # Validate basic fields
                error_reason = diagnose_invalid_metric(config)
                if error_reason and error_reason != "unknown validation error":
                    # Create error result for invalid metric
                    invalid_key = f"InvalidMetric_{i}"
                    invalid_metric_results[invalid_key] = {
                        "score": 0.0,
                        "reason": f"Invalid metric configuration: {error_reason}",
                        "is_successful": False,
                        "threshold": 0.0,
                        "backend": config.get("backend", "unknown")
                        if isinstance(config, dict)
                        else getattr(config, "backend", "unknown"),
                        "name": config.get("name", invalid_key)
                        if isinstance(config, dict)
                        else getattr(config, "name", invalid_key),
                        "class_name": config.get("class_name", "Unknown")
                        if isinstance(config, dict)
                        else getattr(config, "class_name", "Unknown"),
                        "description": f"Failed to load metric: {error_reason}",
                        "error": error_reason,
                    }
                    logger.warning(f"Invalid metric configuration {i}: {error_reason}")
                else:
                    metric_configs.append(config)
            else:
                # Invalid config type
                invalid_key = f"InvalidMetric_{i}"
                invalid_metric_results[invalid_key] = {
                    "score": 0.0,
                    "reason": f"Invalid config type: {type(config).__name__}",
                    "is_successful": False,
                    "threshold": 0.0,
                    "backend": "unknown",
                    "name": invalid_key,
                    "class_name": "Unknown",
                    "description": f"Invalid config type: {type(config).__name__}",
                    "error": f"Invalid config type: {type(config).__name__}",
                }
                logger.warning(f"Invalid config type for metric {i}: {type(config).__name__}")

        # Log summary
        if invalid_metric_results:
            logger.warning(
                f"Found {len(invalid_metric_results)} invalid metrics that will be reported as errors"
            )

        logger.debug(
            f"Using {len(metric_configs)} valid metrics and {len(invalid_metric_results)} invalid metrics"
        )

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

        # Prepare metrics for evaluation
        metric_tasks = self._prepare_metrics(metric_configs, expected_output)

        # Execute metrics in parallel and collect results
        results = self._execute_metrics_in_parallel(
            metric_tasks, input_text, output_text, expected_output, context, max_workers
        )

        # Merge invalid metric results into the final results
        results.update(invalid_metric_results)

        return results

    def _prepare_metrics(
        self, metrics: List[Optional[MetricConfig]], expected_output: Optional[str]
    ) -> List[Tuple[str, BaseMetric, MetricConfig, str]]:
        """
        Prepare metrics for evaluation.

        Args:
            metrics: List of metric configurations (may contain None values)
            expected_output: The expected output (to check if ground truth is required)

        Returns:
            List of tuples containing (class_name, metric_instance, metric_config, backend)
        """
        logger.debug(f"🔍 [DEBUG EVALUATOR] _prepare_metrics called with {len(metrics)} metrics")
        # Filter out any None values that might have slipped through
        valid_metrics = [metric for metric in metrics if metric is not None]
        logger.debug(f"🔍 [DEBUG EVALUATOR] Filtered to {len(valid_metrics)} valid metrics")

        logger.info(f"Preparing {len(valid_metrics)} metrics for evaluation")
        metric_tasks = []

        for metric_config in valid_metrics:
            # Handle both dict and MetricConfig objects
            if isinstance(metric_config, dict):
                class_name = metric_config.get("class_name")
                backend = metric_config.get("backend")
                threshold = metric_config.get("threshold")
                parameters = metric_config.get("parameters", {})
                model_id = metric_config.get("model_id")
            else:
                class_name = metric_config.class_name
                backend = metric_config.backend
                threshold = metric_config.threshold
                parameters = (
                    metric_config.parameters if hasattr(metric_config, "parameters") else {}
                )
                model_id = metric_config.model_id if hasattr(metric_config, "model_id") else None

            try:
                # Validate essential metric configuration
                if not class_name:
                    logger.error(f"Metric configuration missing class_name: {metric_config}")
                    continue

                if not backend:
                    logger.error(f"Metric configuration missing backend: {metric_config}")
                    continue

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
                            logger.info(
                                f"[METRIC_MODEL] Using metric-specific model for '{self._get_config_value(metric_config, 'name', class_name)}': "
                                f"{model_record.name} (provider={model_record.provider_type.type_value}, "
                                f"model={model_record.model_name})"
                            )
                        else:
                            logger.warning(
                                f"[METRIC_MODEL] Model ID {model_id} not found for metric '{self._get_config_value(metric_config, 'name', class_name)}'"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[METRIC_MODEL] Error fetching metric-specific model for '{self._get_config_value(metric_config, 'name', class_name)}': {e}"
                        )

                # 2. Fall back to user's default evaluation model if no metric-specific model
                if metric_model is None and self.model is not None:
                    metric_model = self.model
                    logger.debug(
                        f"[METRIC_MODEL] Using user's default model for '{self._get_config_value(metric_config, 'name', class_name)}'"
                    )

                # 3. Pass model to metric if available (will fall back to system default if None)
                if metric_model is not None:
                    metric_params["model"] = metric_model

                # Instantiate the metric using SDK via adapter
                from rhesis.backend.metrics.adapters import create_metric_from_config

                metric_name = (
                    metric_config.get("name")
                    if isinstance(metric_config, dict)
                    else getattr(metric_config, "name", class_name)
                )
                logger.debug(
                    f"🔍 [DEBUG EVALUATOR] About to create metric via adapter: {metric_name or class_name}"
                )
                logger.debug(
                    f"🔍 [DEBUG EVALUATOR] metric_config type: {type(metric_config)}"
                )
                logger.debug(f"[SDK_ADAPTER] Creating metric via SDK adapter: {metric_name or class_name}")
                
                logger.debug(f"🔍 [DEBUG EVALUATOR] Calling create_metric_from_config...")
                metric = create_metric_from_config(
                    metric_config.to_dict() if hasattr(metric_config, "to_dict") else metric_config,
                    self.organization_id,
                )
                logger.debug(f"🔍 [DEBUG EVALUATOR] create_metric_from_config returned: {type(metric) if metric else None}")
                
                if metric is None:
                    metric_name = (
                        metric_config.get("name")
                        if isinstance(metric_config, dict)
                        else getattr(metric_config, "name", class_name)
                    )
                    logger.error(
                        f"[SDK_ADAPTER] Failed to create metric '{metric_name or class_name}' via adapter"
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
                # Create a more informative error message that includes backend and metric name
                metric_name = (
                    metric_config.get("name")
                    if isinstance(metric_config, dict)
                    else getattr(metric_config, "name", class_name)
                )
                error_msg = (
                    f"Error preparing metric '{metric_name or class_name}' (class: '{class_name}', "
                    f"backend: '{backend}'): {str(e)}"
                )
                logger.error(error_msg, exc_info=True)

        return metric_tasks

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
        Execute metrics in parallel using ThreadPoolExecutor.

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
        results = {}

        if not metric_tasks:
            logger.warning("No metrics to evaluate")
            return results

        logger.info(f"Starting parallel evaluation of {len(metric_tasks)} metrics using threads")

        # Generate unique keys for each metric to avoid collisions
        metric_keys = []
        used_keys = set()  # Track all used keys to ensure uniqueness
        class_name_counts = {}

        for class_name, metric, metric_config, backend in metric_tasks:
            # Start with the preferred key (name if available, otherwise class_name)
            metric_name = (
                metric_config.get("name")
                if isinstance(metric_config, dict)
                else getattr(metric_config, "name", None)
            )
            if metric_name and metric_name.strip():
                base_key = metric_name
            else:
                base_key = class_name

            # Ensure the key is unique by adding suffixes if necessary
            unique_key = base_key
            counter = 1
            while unique_key in used_keys:
                unique_key = f"{base_key}_{counter}"
                counter += 1

            # Track this key as used
            used_keys.add(unique_key)
            metric_keys.append(unique_key)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_metric = {
                executor.submit(
                    self._evaluate_metric, metric, input_text, output_text, expected_output, context
                ): (unique_key, class_name, metric_config, backend)
                for (class_name, metric, metric_config, backend), unique_key in zip(
                    metric_tasks, metric_keys
                )
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_metric):
                unique_key, class_name, metric_config, backend = future_to_metric[future]
                results[unique_key] = self._process_metric_result(
                    future, class_name, metric_config, backend
                )

        logger.info(f"Completed parallel evaluation of {len(results)} metrics")
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
        if 'input' in params:
            kwargs['input'] = input_text
        if 'output' in params:
            kwargs['output'] = output_text
        if 'expected_output' in params:
            kwargs['expected_output'] = expected_output
        if 'context' in params:
            kwargs['context'] = context
            
        logger.debug(
            f"Calling metric '{metric.name}' with parameters: {list(kwargs.keys())}"
        )
        
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
            # Get description from config or use a default
            description = (
                self._get_config_value(metric_config, "description")
                or f"{class_name} evaluation metric"
            )

            # Calculate is_successful using the score evaluator
            is_successful = self.score_evaluator.evaluate_score(
                score=result.score,
                threshold=self._get_config_value(metric_config, "threshold"),
                threshold_operator=self._get_config_value(metric_config, "threshold_operator"),
                reference_score=self._get_config_value(metric_config, "reference_score"),
            )

            # Store results - structure depends on metric type
            processed_result = {
                "score": result.score,
                "reason": result.details.get("reason", f"Score: {result.score}"),
                "is_successful": is_successful,
                "backend": backend,
                "name": self._get_config_value(metric_config, "name"),
                "class_name": class_name,  # Include class_name for identification
                "description": description,
            }

            # Add threshold or reference_score based on metric type
            threshold = self._get_config_value(metric_config, "threshold")
            reference_score = self._get_config_value(metric_config, "reference_score")
            if threshold is not None:
                # Numeric metric - include threshold
                processed_result["threshold"] = threshold
            elif reference_score is not None:
                # Binary/categorical metric - include reference_score
                processed_result["reference_score"] = reference_score

            logger.debug(f"Completed metric '{class_name}' with score {result.score}")
            return processed_result

        except Exception as exc:
            import traceback

            logger.error(f"Metric '{class_name}' generated an exception: {exc}", exc_info=True)
            logger.error(f"Backend: {backend}")
            logger.error(f"Metric config: {metric_config}")
            logger.error(f"Exception type: {type(exc).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            # Store error information in results
            error_result = {
                "score": 0.0,
                "reason": f"Error: {str(exc)}",
                "is_successful": False,
                "backend": backend,
                "name": self._get_config_value(metric_config, "name"),
                "class_name": class_name,  # Include class_name for identification
                "description": description
                if "description" in locals()
                else f"{class_name} evaluation metric",
                "error": str(exc),
                "exception_type": type(exc).__name__,
            }

            # Add threshold or reference_score for error results too
            threshold = self._get_config_value(metric_config, "threshold")
            reference_score = self._get_config_value(metric_config, "reference_score")
            if threshold is not None:
                error_result["threshold"] = threshold
            elif reference_score is not None:
                error_result["reference_score"] = reference_score

            return error_result
