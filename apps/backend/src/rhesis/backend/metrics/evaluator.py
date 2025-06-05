import concurrent.futures
import operator
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.base import BaseMetric, MetricConfig, MetricResult

# Use inline factory creation to avoid circular imports
# Implementation of the factory import will be delayed until needed


class ScoreType(str, Enum):
    BINARY = "binary"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


# Mapping threshold operators to Python operator functions
OPERATOR_MAP = {
    ThresholdOperator.EQUAL: operator.eq,
    ThresholdOperator.LESS_THAN: operator.lt,
    ThresholdOperator.GREATER_THAN: operator.gt,
    ThresholdOperator.LESS_THAN_OR_EQUAL: operator.le,
    ThresholdOperator.GREATER_THAN_OR_EQUAL: operator.ge,
    ThresholdOperator.NOT_EQUAL: operator.ne,
}

# Valid operators for different score types
VALID_OPERATORS_BY_SCORE_TYPE = {
    ScoreType.BINARY: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.CATEGORICAL: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.NUMERIC: set(ThresholdOperator),  # All operators are valid for numeric
}

# Legacy mapping for string operators (for backward compatibility)
THRESHOLD_OPERATOR_MAP = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
    "==": operator.eq,
    "!=": operator.ne,
    "<>": operator.ne,
}

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

    def _sanitize_threshold_operator(self, threshold_operator: Union[ThresholdOperator, str, None]) -> Optional[ThresholdOperator]:
        """
        Sanitize and validate the threshold operator.
        
        Args:
            threshold_operator: The threshold operator to sanitize
            
        Returns:
            ThresholdOperator: Sanitized and validated threshold operator, or None if invalid
            
        Raises:
            ValueError: If the operator is invalid
        """
        if threshold_operator is None:
            return None
            
        # Trim whitespace if it's a string
        if isinstance(threshold_operator, str):
            threshold_operator = threshold_operator.strip()
            
        # Convert string to enum if needed
        if isinstance(threshold_operator, str):
            try:
                threshold_operator = ThresholdOperator(threshold_operator)
            except ValueError:
                logger.warning(f"Invalid threshold operator: '{threshold_operator}'. "
                             f"Valid operators are: {', '.join([op.value for op in ThresholdOperator])}")
                return None
        
        # Validate that it's a valid ThresholdOperator
        if not isinstance(threshold_operator, ThresholdOperator):
            logger.warning(f"threshold_operator must be a ThresholdOperator enum or valid string, "
                         f"got {type(threshold_operator)}")
            return None
            
        return threshold_operator
    
    def _validate_operator_for_score_type(self, threshold_operator: ThresholdOperator, score_type: ScoreType) -> bool:
        """
        Validate that the threshold operator is appropriate for the score type.
        
        Args:
            threshold_operator: The threshold operator to validate
            score_type: The score type to validate against
            
        Returns:
            bool: True if the operator is valid for the score type
        """
        valid_operators = VALID_OPERATORS_BY_SCORE_TYPE.get(score_type, set())
        if threshold_operator not in valid_operators:
            valid_ops_str = ', '.join([op.value for op in valid_operators])
            logger.warning(f"Operator '{threshold_operator.value}' is not valid for score type '{score_type.value}'. "
                         f"Valid operators for {score_type.value} are: {valid_ops_str}")
            return False
        return True

    def _determine_score_type(self, score: Union[float, str, int], threshold_operator: Optional[str]) -> ScoreType:
        """
        Determine the score type based on the score value and threshold operator.
        
        Args:
            score: The score value
            threshold_operator: The threshold operator
            
        Returns:
            ScoreType: The determined score type
        """
        # If it's a string score, determine if it's binary or categorical
        if isinstance(score, str):
            # Common binary values
            binary_values = {"true", "false", "yes", "no", "pass", "fail", "success", "failure", "1", "0"}
            if score.lower().strip() in binary_values:
                return ScoreType.BINARY
            else:
                return ScoreType.CATEGORICAL
        
        # If it's numeric, it's numeric type
        return ScoreType.NUMERIC

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
                    # Create a more informative error message that includes backend and metric name
                    metric_name = config.get("name") or config.get("class_name")
                    error_msg = (f"Error parsing metric configuration (class: '{metric_name}', "
                               f"backend: '{config.get('backend')}'): {str(e)}")
                    logger.error(error_msg, exc_info=True)
                    invalid_key = f"InvalidMetric_{i}"
                    invalid_metric_results[invalid_key] = {
                        "score": 0.0,
                        "reason": error_msg,
                        "is_successful": False,
                        "threshold": 0.0,
                        "backend": config.get("backend", "unknown") if isinstance(config, dict) else "unknown",
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
                # Create a more informative error message that includes backend and metric name
                metric_name = metric_config.name or class_name
                error_msg = (f"Error preparing metric '{metric_name}' (class: '{class_name}', "
                           f"backend: '{backend}'): {str(e)}")
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
            
            # Calculate is_successful based on threshold operator from database
            is_successful = self.evaluate_score(
                score=result.score,
                threshold=metric_config.threshold,
                threshold_operator=metric_config.threshold_operator,
                reference_score=metric_config.reference_score
            )
            
            # Store results
            processed_result = {
                "score": result.score,
                "reason": result.details["reason"],
                "is_successful": is_successful,
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

    def evaluate_score(
        self,
        score: Union[float, str, int],
        threshold: Optional[float],
        threshold_operator: Optional[str],
        reference_score: Optional[str] = None,
        score_type: Optional[Union[ScoreType, str]] = None
    ) -> bool:
        """
        Evaluate whether a metric score meets the success criteria based on threshold and operator.
        This method incorporates all the functionality from metric_base.py for comprehensive score evaluation.
        
        Args:
            score: The metric score (can be numeric or string)
            threshold: The threshold value for numeric scores
            threshold_operator: The comparison operator ('<', '>', '>=', '<=', '=', '!=')
            reference_score: Reference score for binary/categorical metrics
            score_type: Explicit score type, if not provided will be auto-determined
            
        Returns:
            bool: True if the metric score meets the success criteria
        """
        # Determine score type if not provided
        if score_type is None:
            score_type = self._determine_score_type(score, threshold_operator)
        elif isinstance(score_type, str):
            try:
                score_type = ScoreType(score_type)
            except ValueError:
                logger.warning(f"Invalid score type '{score_type}', auto-determining from score")
                score_type = self._determine_score_type(score, threshold_operator)
        
        # Sanitize and validate threshold operator
        sanitized_operator = self._sanitize_threshold_operator(threshold_operator)
        
        # Set default threshold operator based on score type if none provided or invalid
        if sanitized_operator is None:
            if score_type == ScoreType.NUMERIC:
                sanitized_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
            else:  # BINARY or CATEGORICAL
                sanitized_operator = ThresholdOperator.EQUAL
            logger.debug(f"Using default operator '{sanitized_operator.value}' for score type '{score_type.value}'")
        
        # Validate operator for score type
        if not self._validate_operator_for_score_type(sanitized_operator, score_type):
            # Fall back to appropriate default if validation fails
            if score_type == ScoreType.NUMERIC:
                sanitized_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
            else:
                sanitized_operator = ThresholdOperator.EQUAL
            logger.debug(f"Falling back to operator '{sanitized_operator.value}' for score type '{score_type.value}'")
        
        # Handle different score types
        if score_type == ScoreType.NUMERIC:
            return self._evaluate_numeric_score(score, threshold, sanitized_operator)
        else:  # BINARY or CATEGORICAL
            return self._evaluate_categorical_score(score, reference_score, threshold, sanitized_operator)

    def _evaluate_numeric_score(
        self,
        score: Union[float, int],
        threshold: Optional[float],
        threshold_operator: ThresholdOperator
    ) -> bool:
        """
        Evaluate numeric scores against threshold using the specified operator.
        
        Args:
            score: The numeric score
            threshold: The threshold value
            threshold_operator: The comparison operator
            
        Returns:
            bool: True if the score meets the criteria
        """
        # Convert score to float if it's not already
        try:
            numeric_score = float(score)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert score '{score}' to numeric value")
            return False
        
        # Validate threshold is provided for numeric scores
        if threshold is None:
            logger.warning("Threshold is required for numeric score type but was not provided")
            return False
        
        # Use operator module for comparison
        op_func = OPERATOR_MAP.get(threshold_operator)
        if op_func is None:
            # Fallback to default behavior
            logger.warning(f"Unknown operator '{threshold_operator}', defaulting to '>='")
            return numeric_score >= threshold
            
        return op_func(numeric_score, threshold)

    def _evaluate_categorical_score(
        self,
        score: Union[str, float, int],
        reference_score: Optional[str],
        threshold: Optional[float],
        threshold_operator: ThresholdOperator
    ) -> bool:
        """
        Evaluate binary/categorical scores against reference score using the specified operator.
        
        Args:
            score: The score value
            reference_score: The reference score to compare against
            threshold: The threshold (used as reference if reference_score not provided)
            threshold_operator: The comparison operator
            
        Returns:
            bool: True if the score meets the criteria
        """
        # Determine reference value
        if reference_score is None:
            if threshold is not None:
                reference_value = str(threshold)
            else:
                logger.warning("Reference score or threshold is required for binary/categorical score type but was not provided")
                return False
        else:
            reference_value = reference_score
        
        # Convert score to string for comparison
        score_str = str(score).lower().strip() if not isinstance(score, str) else score.lower().strip()
        reference_str = reference_value.lower().strip()
        
        # Use operator module for comparison
        op_func = OPERATOR_MAP.get(threshold_operator)
        if op_func is None:
            # Fallback to equality check
            logger.warning(f"Unknown operator '{threshold_operator}', defaulting to equality")
            return score_str == reference_str
            
        return op_func(score_str, reference_str)

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
