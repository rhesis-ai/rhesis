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

        # Convert any dict configs to MetricConfig objects
        metric_configs = [
            config if isinstance(config, MetricConfig) else MetricConfig.from_dict(config)
            for config in metrics
        ]

        # Prepare metrics for evaluation
        metric_tasks = self._prepare_metrics(metric_configs, expected_output)

        # Execute metrics in parallel and collect results
        results = self._execute_metrics_in_parallel(
            metric_tasks, input_text, output_text, expected_output, context, max_workers
        )

        return results

    def _prepare_metrics(
        self, metrics: List[MetricConfig], expected_output: Optional[str]
    ) -> List[Tuple[str, BaseMetric, MetricConfig, str]]:
        """
        Prepare metrics for evaluation.

        Args:
            metrics: List of metric configurations
            expected_output: The expected output (to check if ground truth is required)

        Returns:
            List of tuples containing (class_name, metric_instance, metric_config, backend)
        """
        logger.info(f"Preparing {len(metrics)} metrics for evaluation")
        metric_tasks = []

        for metric_config in metrics:
            class_name = metric_config.class_name
            backend = metric_config.backend

            try:
                # Prepare parameters for the metric
                metric_params = {
                    "threshold": metric_config.threshold,
                    **metric_config.parameters
                }

                # Instantiate the metric using the class name and backend
                metric = self._get_factory().create(backend, class_name, **metric_params)

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

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_metric = {
                executor.submit(
                    self._evaluate_metric, metric, input_text, output_text, expected_output, context
                ): (class_name, metric_config, backend)
                for class_name, metric, metric_config, backend in metric_tasks
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_metric):
                class_name, metric_config, backend = future_to_metric[future]
                results[class_name] = self._process_metric_result(
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
                "description": description if 'description' in locals() else f"{class_name} evaluation metric",
                "error": str(exc),
            }


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
