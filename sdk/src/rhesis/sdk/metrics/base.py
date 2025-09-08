"""

TODO:
These strings are spread all over the class as strings. Can we optimize this?


# Extract all other keys as custom parameters
reserved_keys = {
    "class_name",
    "backend",
    "threshold",
    "reference_score",
    "threshold_operator",
    "description",
    "name",
}
Also, the method retry_evaluationmight be better placed in a utils type of module?
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar, Union

import tenacity

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model

MetricType = Literal["rag", "generation", "classification"]
F = TypeVar("F", bound=Callable[..., Any])


def retry_evaluation(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
    retry_max_delay: float = 30.0,
    retry_exceptions: tuple = (ConnectionError, TimeoutError),
) -> Callable[[F], F]:
    """
    Decorator that adds retry logic to evaluation methods.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        retry_backoff: Exponential backoff multiplier
        retry_max_delay: Maximum delay between retries
        retry_exceptions: Exception types that should trigger a retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            @tenacity.retry(
                stop=tenacity.stop_after_attempt(max_retries),
                wait=tenacity.wait_exponential(
                    multiplier=retry_delay, exp_base=retry_backoff, max=retry_max_delay
                ),
                retry=tenacity.retry_if_exception_type(retry_exceptions),
            )
            def _execute_with_retry():
                return func(*args, **kwargs)

            return _execute_with_retry()

        return wrapper

    return decorator


@dataclass
class MetricConfig:
    """Standard configuration for a metric instance."""

    class_name: str
    """The class name of the metric to instantiate (e.g., 'DeepEvalContextualRecall')"""

    backend: str
    """The backend/framework to use for this metric (e.g., 'deepeval')"""

    threshold: Optional[float] = None
    """Threshold for metric success (used for numeric score types)"""

    reference_score: Optional[str] = None
    """Reference score for binary/categorical metrics (e.g., 'true', 'excellent')"""

    threshold_operator: Optional[str] = None
    """Threshold operator for comparison (e.g., '>=', '<', '=')"""

    name: Optional[str] = None
    """Human-readable name of the metric"""

    description: Optional[str] = None
    """Human-readable description of what the metric measures"""

    parameters: Dict[str, Any] = field(default_factory=dict)
    """Additional parameters specific to this metric implementation"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the config to a dictionary."""
        result = {
            "class_name": self.class_name,
            "backend": self.backend,
        }

        if self.threshold is not None:
            result["threshold"] = self.threshold

        if self.reference_score is not None:
            result["reference_score"] = self.reference_score

        if self.threshold_operator is not None:
            result["threshold_operator"] = self.threshold_operator

        if self.description:
            result["description"] = self.description

        # Add any custom parameters
        result.update(self.parameters)

        return result

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["MetricConfig"]:
        """Create a MetricConfig from a dictionary.

        Args:
            data: Dictionary containing metric configuration data

        Returns:
            MetricConfig instance or None if data is invalid

        Raises:
            ValueError: If data has invalid structure but is not None
        """
        if data is None:
            return None

        if not isinstance(data, dict):
            raise ValueError(f"Expected dictionary for metric config, got {type(data)}")

        # Check for required fields
        required_fields = ["class_name", "backend"]
        missing_fields = [
            field for field in required_fields if field not in data or data[field] is None
        ]

        if missing_fields:
            # Return None for invalid configs rather than raising an exception
            # This allows the calling code to handle invalid metrics gracefully
            return None

        # Extract required fields
        class_name = data["class_name"]
        backend = data["backend"]

        # Validate that required fields are not empty strings
        if not class_name.strip() if isinstance(class_name, str) else not class_name:
            return None

        if not backend.strip() if isinstance(backend, str) else not backend:
            return None

        # Extract optional fields with defaults
        threshold = data.get("threshold")
        reference_score = data.get("reference_score")
        threshold_operator = data.get("threshold_operator")
        description = data.get("description")
        name = data.get("name")

        # Ensure threshold is a valid number if provided
        if threshold is not None:
            try:
                threshold = float(threshold)
            except (ValueError, TypeError):
                threshold = None

        # Extract all other keys as custom parameters
        reserved_keys = {
            "class_name",
            "backend",
            "threshold",
            "reference_score",
            "threshold_operator",
            "description",
            "name",
        }
        parameters = {k: v for k, v in data.items() if k not in reserved_keys}

        return cls(
            class_name=class_name,
            backend=backend,
            threshold=threshold,
            reference_score=reference_score,
            threshold_operator=threshold_operator,
            description=description,
            name=name,
            parameters=parameters,
        )


class MetricResult:
    """Result of a metric evaluation."""

    def __init__(self, score: float, details: Dict[str, Any] = None):
        self.score = score
        self.details = details or {}

    def __str__(self):
        return f"MetricResult(score={self.score}, details={self.details})"


class BaseMetric(ABC):
    """Base class for all evaluation metrics."""

    def __init__(
        self,
        name: str,
        metric_type: MetricType = "rag",
        model: Optional[Union[BaseLLM, str]] = None,
        **kwargs,
    ):
        self._name = name
        self._metric_type = metric_type
        if isinstance(model, BaseLLM):
            self._model = model
        elif isinstance(model, str) or model is None:
            self._model = get_model(model)
        else:
            raise ValueError(f"Invalid model type: {type(model)}")

    @property
    def name(self) -> str:
        return self._name

    @property
    def metric_type(self) -> MetricType:
        return self._metric_type

    @property
    @abstractmethod
    def requires_ground_truth(self) -> bool:
        """Whether this metric requires a ground truth reference."""
        pass

    @abstractmethod
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        """
        Evaluate the metric on the given input, output, and context.

        Args:
            input: The input query/question
            output: The system output/response
            expected_output: The expected or reference output (ground truth)
            context: List of context chunks used for the response

        Returns:
            MetricResult: The evaluation result
        """
        pass


class BaseMetricFactory(ABC):
    """Base factory interface for creating metric instances."""

    @abstractmethod
    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance of the specified type."""
        pass

    @abstractmethod
    def list_supported_metrics(self) -> List[str]:
        """List all supported metric types for this factory."""
        pass
