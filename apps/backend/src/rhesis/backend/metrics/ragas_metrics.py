from typing import List, Optional

from .base import BaseMetric, BaseMetricFactory, MetricResult, MetricType


class RagasMetricBase(BaseMetric):
    """Base class for Ragas metrics with common functionality."""

    def __init__(self, name: str, threshold: float = 0.5, metric_type: MetricType = "rag"):
        super().__init__(name=name, metric_type=metric_type)
        self._threshold = threshold
        # Actual Ragas implementation to be added

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        if not 0 <= value <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self._threshold = value


class RagasAnswerRelevancy(RagasMetricBase):
    """Ragas implementation of Answer Relevancy metric."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="answer_relevancy", threshold=threshold, metric_type="rag")
        # Initialize Ragas specific implementation

    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        # Implement Ragas specific evaluation logic
        # Placeholder implementation
        return MetricResult(
            score=0.0,
            details={
                "reason": "Not implemented yet",
                "is_successful": False,
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return True


class RagasContextualPrecision(RagasMetricBase):
    """Ragas implementation of Contextual Precision metric."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="contextual_precision", threshold=threshold, metric_type="rag")
        # Initialize Ragas specific implementation

    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        # Implement Ragas specific evaluation logic
        # Placeholder implementation
        return MetricResult(
            score=0.0,
            details={
                "reason": "Not implemented yet",
                "is_successful": False,
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class RagasMetricFactory(BaseMetricFactory):
    """Factory for creating Ragas metric instances."""

    _metrics = {
        "RagasAnswerRelevancy": RagasAnswerRelevancy,
        "RagasContextualPrecision": RagasContextualPrecision,
    }

    # Define which parameters each metric class accepts
    _supported_params = {
        "RagasAnswerRelevancy": {"threshold"},
        "RagasContextualPrecision": {"threshold"},
    }

    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance using class name.
        
        Args:
            class_name: The class name to instantiate (e.g., 'RagasContextualPrecision')
            **kwargs: Additional parameters to pass to the class constructor
            
        Returns:
            BaseMetric: An instance of the specified metric class
            
        Raises:
            ValueError: If the specified class doesn't exist in this module
        """
        if class_name not in self._metrics:
            available_classes = list(self._metrics.keys())
            raise ValueError(
                f"Unknown metric class: {class_name}. Available classes: {available_classes}"
            )

        # Filter kwargs to only include supported parameters for this class
        supported_params = self._supported_params.get(class_name, set())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported_params}
        
        return self._metrics[class_name](**filtered_kwargs)

    def list_supported_metrics(self) -> List[str]:
        """List available metric class names."""
        return list(self._metrics.keys())
