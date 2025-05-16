from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

MetricType = Literal["rag", "llm", "general"]  # Add more types as needed


@dataclass
class MetricResult:
    """Result from a metric computation."""

    score: float
    details: Dict[str, Any]


class BaseMetric(ABC):
    """Base class for all metrics."""

    def __init__(self, name: str, metric_type: MetricType = "rag"):
        self.name = name
        self.metric_type = metric_type
        self._threshold = 0.5
        self._strict_mode = False
        self._verbose_mode = False
        self._requires_ground_truth = True

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        if not 0 <= value <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self._threshold = value

    @property
    def strict_mode(self) -> bool:
        return self._strict_mode

    @strict_mode.setter
    def strict_mode(self, value: bool):
        self._strict_mode = value

    @property
    def verbose_mode(self) -> bool:
        return self._verbose_mode

    @verbose_mode.setter
    def verbose_mode(self, value: bool):
        self._verbose_mode = value

    @property
    def requires_ground_truth(self) -> bool:
        """Whether this metric requires ground truth (expected output) to compute."""
        return self._requires_ground_truth

    @abstractmethod
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        """Evaluate the metric.

        Args:
            input: The input query or question
            output: The actual output from the LLM
            expected_output: The expected or reference output
            context: List of context strings used for the response

        Returns:
            MetricResult containing the score and additional details
        """
        pass


class BaseMetricFactory(ABC):
    """Base class for metric factories."""

    @abstractmethod
    def create(self, metric_type: str, **kwargs) -> BaseMetric:
        """Create a metric instance.

        Args:
            metric_type: Type of metric to create
            **kwargs: Additional keyword arguments

        Returns:
            BaseMetric: The metric instance

        Raises:
            ValueError: If metric_type is not supported
        """
        pass

    @abstractmethod
    def list_supported_metrics(self) -> List[str]:
        """List all supported metric types for this factory.

        Returns:
            List[str]: List of supported metric types
        """
        pass
