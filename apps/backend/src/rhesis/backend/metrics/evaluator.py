import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple, Union

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.base import BaseMetric, MetricConfig, MetricResult

# Use inline factory creation to avoid circular imports
# Implementation of the factory import will be delayed until needed

class MetricEvaluator:
    """Evaluator class that handles metric computation using configured backends."""

    def __init__(self):
        """Initialize evaluator with factory."""
        # Lazy load factory to avoid circular imports
        self.factory = None

    def _get_factory(self):
        """Lazy load the MetricFactory to avoid circular imports."""
        if self.factory is None:
            from rhesis.backend.metrics.factory import MetricFactory
            self.factory = MetricFactory()
        return self.factory

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
        if not metrics:
            logger.warning("No metrics provided for evaluation")
            return {}

        # Convert any dict configs to MetricConfig objects, keeping track of invalid ones
        metric_configs = []
        invalid_metric_results = {}  # Store results for invalid metrics
        
        for i, config in enumerate(metrics):
            if isinstance(config, MetricConfig):
                metric_configs.append(config)
            else:
                try:
                    parsed_config = MetricConfig.from_dict(config)
                    if parsed_config is not None:
                        metric_configs.append(parsed_config)
                    else:
                        # Create error result for invalid metric
                        error_reason = self._diagnose_invalid_metric(config)
                        invalid_key = f"InvalidMetric_{i}"
                        invalid_metric_results[invalid_key] = {
                            "score": 0.0,
                            "reason": f"Invalid metric configuration: {error_reason}",
                            "is_successful": False,
                            "threshold": 0.0,
                            "backend": config.get("backend", "unknown") if isinstance(config, dict) else "unknown",
                            "name": config.get("name", invalid_key) if isinstance(config, dict) else invalid_key,
                            "class_name": config.get("class_name", "Unknown") if isinstance(config, dict) else "Unknown",
                            "description": f"Failed to load metric: {error_reason}",
                            "error": error_reason,
                        }
                        logger.warning(f"Invalid metric configuration {i}: {error_reason}")
                except Exception as e:
                    # Create error result for parsing failure
                    error_reason = f"Failed to parse metric configuration: {str(e)}"
                    invalid_key = f"InvalidMetric_{i}"
                    invalid_metric_results[invalid_key] = {
                        "score": 0.0,
                        "reason": error_reason,
                        "is_successful": False,
                        "threshold": 0.0,
                        "backend": "unknown",
                        "name": invalid_key,
                        "class_name": config.get("class_name", "Unknown") if isinstance(config, dict) else "Unknown",
                        "description": f"Parsing error: {str(e)}",
                        "error": str(e),
                    }
                    logger.warning(f"Failed to parse metric configuration {i}: {str(e)}")

        # Log summary
        if invalid_metric_results:
            logger.warning(f"Found {len(invalid_metric_results)} invalid metrics that will be reported as errors")
        
        logger.debug(f"Using {len(metric_configs)} valid metrics and {len(invalid_metric_results)} invalid metrics")

        if not metric_configs:
            logger.warning("No valid metrics found after parsing")
            if invalid_metric_results:
                logger.warning(f"Returning {len(invalid_metric_results)} invalid metrics as error results")
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
        # Filter out any None values that might have slipped through
        valid_metrics = [metric for metric in metrics if metric is not None]
        
        logger.info(f"Preparing {len(valid_metrics)} metrics for evaluation")
        metric_tasks = []

        for metric_config in valid_metrics:
            class_name = metric_config.class_name
            backend = metric_config.backend

            try:
                # Validate essential metric configuration
                if not class_name:
                    logger.error(f"Metric configuration missing class_name: {metric_config}")
                    continue
                    
                if not backend:
                    logger.error(f"Metric configuration missing backend: {metric_config}")
                    continue

                # Prepare parameters for the metric
                metric_params = {
                    "threshold": metric_config.threshold,
                    **metric_config.parameters
                }

                # Instantiate the metric using the class name and backend
                backend_factory = self._get_factory().get_factory(backend)
                metric = backend_factory.create(class_name, **metric_params)

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
                logger.error(f"Error preparing metric '{class_name}': {str(e)}", exc_info=True)

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
            if metric_config.name and metric_config.name.strip():
                base_key = metric_config.name
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
                for (class_name, metric, metric_config, backend), unique_key in zip(metric_tasks, metric_keys)
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_metric):
                unique_key, class_name, metric_config, backend = future_to_metric[future]
                results[unique_key] = self._process_metric_result(
                    future, class_name, metric_config, backend
                )

        logger.info(f"Completed parallel evaluation of {len(results)} metrics")
        return results

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
        return metric.evaluate(
            input=input_text, output=output_text, expected_output=expected_output, context=context
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
            description = metric_config.description or f"{class_name} evaluation metric"
            
            # Store results
            processed_result = {
                "score": result.score,
                "reason": result.details["reason"],
                "is_successful": result.details["is_successful"],
                "threshold": metric_config.threshold,
                "backend": backend,
                "name": metric_config.name,
                "class_name": class_name,  # Include class_name for identification
                "description": description,
            }
            logger.debug(f"Completed metric '{class_name}' with score {result.score:.2f}")
            return processed_result

        except Exception as exc:
            logger.error(f"Metric '{class_name}' generated an exception: {exc}", exc_info=True)
            # Store error information in results
            return {
                "score": 0.0,
                "reason": f"Error: {str(exc)}",
                "is_successful": False,
                "threshold": metric_config.threshold,
                "backend": backend,
                "name": metric_config.name,
                "class_name": class_name,  # Include class_name for identification
                "description": description if 'description' in locals() else f"{class_name} evaluation metric",
                "error": str(exc),
            }

    def _diagnose_invalid_metric(self, config: Union[Dict[str, Any], MetricConfig]) -> str:
        """
        Diagnose the reason why a metric configuration is invalid.

        Args:
            config: The metric configuration

        Returns:
            A string describing the reason why the metric configuration is invalid
        """
        if config is None:
            return "configuration is None"
            
        if isinstance(config, MetricConfig):
            missing_fields = []
            if not config.class_name or (isinstance(config.class_name, str) and not config.class_name.strip()):
                missing_fields.append("class_name")
            if not config.backend or (isinstance(config.backend, str) and not config.backend.strip()):
                missing_fields.append("backend")
            if missing_fields:
                return f"missing or empty required fields: {', '.join(missing_fields)}"
        elif isinstance(config, dict):
            missing_fields = []
            if "class_name" not in config or config["class_name"] is None or (isinstance(config["class_name"], str) and not config["class_name"].strip()):
                missing_fields.append("class_name")
            if "backend" not in config or config["backend"] is None or (isinstance(config["backend"], str) and not config["backend"].strip()):
                missing_fields.append("backend")
            if missing_fields:
                return f"missing or empty required fields: {', '.join(missing_fields)}"
        else:
            return f"invalid configuration type: {type(config).__name__} (expected dict or MetricConfig)"
            
        return "unknown validation error"


def run_evaluation(
    input_text: str,
    output_text: str,
    expected_output: Optional[str],
    context: List[str],
    metrics: List[Union[Dict[str, Any], MetricConfig]],
    max_workers: int = 5,
) -> Dict[str, Any]:
    """
    Helper function to run the metric evaluation using MetricEvaluator.
    
    Args:
        input_text: The input query or question
        output_text: The actual output from the LLM
        expected_output: The expected or reference output
        context: List of context strings used for the response
        metrics: List of metric configurations (MetricConfig objects or dictionaries)
        max_workers: Maximum number of parallel workers
        
    Returns:
        Dictionary of metric results
    """
    evaluator = MetricEvaluator()
    return evaluator.evaluate(
        input_text=input_text,
        output_text=output_text,
        expected_output=expected_output,
        context=context,
        metrics=metrics,
        max_workers=max_workers,
    )
