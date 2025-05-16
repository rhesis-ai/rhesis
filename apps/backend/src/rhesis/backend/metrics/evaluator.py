import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.base import BaseMetric, MetricResult
from rhesis.backend.metrics.config.loader import MetricConfigLoader
from rhesis.backend.metrics.factory import MetricFactory


class MetricEvaluator:
    """Evaluator class that handles metric computation using configured backends."""

    def __init__(self):
        """Initialize evaluator with configuration."""
        self.config = MetricConfigLoader()
        self.factory = MetricFactory()

    def evaluate(
        self,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        metrics: Optional[List[Dict[str, Any]]] = None,
        max_workers: int = 5,
    ) -> Dict[str, Any]:
        """
        Compute metrics using the configured backends in parallel.

        Args:
            input_text: The input query or question
            output_text: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response
            metrics: List of dicts with metric configs, e.g. 
                    [{"name": "answer_relevancy", "threshold": 0.7}]
                    If None, computes all available metrics with default thresholds
            max_workers: Maximum number of parallel workers for metric computation

        Returns:
            Dictionary containing scores and details for each metric
        """
        # Prepare metrics for evaluation
        metric_tasks = self._prepare_metrics(metrics, expected_output)

        # Execute metrics in parallel and collect results
        results = self._execute_metrics_in_parallel(
            metric_tasks, input_text, output_text, expected_output, context, max_workers
        )

        return results

    def _prepare_metrics(
        self, metrics: Optional[List[Dict[str, Any]]], expected_output: Optional[str]
    ) -> List[Tuple[str, BaseMetric, Dict[str, Any], str]]:
        """
        Prepare metrics for evaluation.

        Args:
            metrics: List of metric configurations
            expected_output: The expected output (to check if ground truth is required)

        Returns:
            List of tuples containing (metric_name, metric_instance, metric_settings, backend)
        """
        # If no metrics specified, use all available ones with default settings
        if metrics is None:
            metrics = [{"name": metric_name} for metric_name in self.config.metrics.keys()]

        logger.info(f"Preparing {len(metrics)} metrics for evaluation")
        metric_tasks = []

        for metric_config in metrics:
            metric_name = metric_config["name"]

            try:
                # Get metric settings from config
                metric_settings = self.config.get_metric_config(metric_name)

                # Get the appropriate factory for this metric's backend
                backend = metric_settings["backend"]
                factory = self.factory.get_factory(backend)

                # Create metric with config-specified defaults, overridden by user settings
                metric_params = {
                    "threshold": metric_settings["default_threshold"],
                    **{k: v for k, v in metric_config.items() if k != "name"},
                }

                metric = factory.create(metric_name, **metric_params)

                # Skip metrics that require ground truth if it's not provided
                if metric.requires_ground_truth and expected_output is None:
                    logger.debug(
                        f"Skipping metric '{metric_name}' as it requires ground truth "
                        f"which is not provided"
                    )
                    continue

                # Add task to the list
                metric_tasks.append((metric_name, metric, metric_settings, backend))

            except Exception as e:
                logger.error(f"Error preparing metric '{metric_name}': {str(e)}", exc_info=True)

        return metric_tasks

    def _execute_metrics_in_parallel(
        self,
        metric_tasks: List[Tuple[str, BaseMetric, Dict[str, Any], str]],
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
                ): (metric_name, metric_settings, backend)
                for metric_name, metric, metric_settings, backend in metric_tasks
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_metric):
                metric_name, metric_settings, backend = future_to_metric[future]
                results[metric_name] = self._process_metric_result(
                    future, metric_name, metric_settings, backend
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
        metric_name: str,
        metric_settings: Dict[str, Any],
        backend: str,
    ) -> Dict[str, Any]:
        """
        Process the result of a metric evaluation.

        Args:
            future: The Future object containing the result
            metric_name: Name of the metric
            metric_settings: Settings for the metric
            backend: Backend used for the metric

        Returns:
            Dictionary with processed metric results
        """
        try:
            result = future.result()
            # Store results
            processed_result = {
                "score": result.score,
                "reason": result.details["reason"],
                "is_successful": result.details["is_successful"],
                "threshold": result.details["threshold"],
                "backend": backend,
                "description": metric_settings["description"],
            }
            logger.debug(f"Completed metric '{metric_name}' with score {result.score:.2f}")
            return processed_result

        except Exception as exc:
            logger.error(f"Metric '{metric_name}' generated an exception: {exc}", exc_info=True)
            # Store error information in results
            return {
                "score": 0.0,
                "reason": f"Error: {str(exc)}",
                "is_successful": False,
                "threshold": metric_settings["default_threshold"],
                "backend": backend,
                "description": metric_settings["description"],
                "error": str(exc),
            }


if __name__ == "__main__":
    # Example usage
    sample_input = {
        "input_text": "What is the capital of France?",
        "output_text": "The capital of France is Paris. It is known as the City of Light.",
        "expected_output": "Paris is the capital of France.",
        "context": [
            "Paris is the capital and largest city of France.",
            "Known as the City of Light, Paris is a global center for art, culture, and fashion.",
        ],
    }

    # Create evaluator
    evaluator = MetricEvaluator()

    # Example 1: Evaluate all metrics with default thresholds
    results_all = evaluator.evaluate(**sample_input)

    # Example 2: Evaluate specific metrics with custom thresholds
    results_specific = evaluator.evaluate(
        metrics=[
            {"name": "answer_relevancy", "threshold": 0.7},
            {"name": "faithfulness", "threshold": 0.8},
        ],
        **sample_input,
    )

    # Print results in a readable format
    def print_results(results: Dict[str, Any], title: str):
        print(f"\n{title}")
        print("=" * len(title))
        for metric_name, metric_results in results.items():
            print(f"\n{metric_name.upper()}:")
            print(f"Description: {metric_results['description']}")
            print(f"Backend: {metric_results['backend']}")
            print(f"Score: {metric_results['score']:.2f}")
            print(f"Success: {metric_results['is_successful']}")
            print(f"Reason: {metric_results['reason']}")
            print(f"Threshold: {metric_results['threshold']}")
            print("-" * 50)

    print_results(results_all, "All Metrics")
    print_results(results_specific, "Specific Metrics")
