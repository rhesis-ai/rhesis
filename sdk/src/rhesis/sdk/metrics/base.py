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
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model

MetricType = Literal["rag", "generation", "classification"]
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class MetricConfig:
    """Standard configuration for a metric instance."""

    class_name: str = "RhesisPromptMetricNumeric"
    """The class name of the metric to instantiate (e.g., 'DeepEvalContextualRecall')"""

    backend: str = "rhesis"
    """The backend/framework to use for this metric (e.g., 'deepeval')"""

    evaluation_prompt: str
    """The evaluation prompt for the metric"""

    evaluation_steps: Optional[str]
    """The evaluation steps for the metric"""

    reasoning: Optional[str]
    """The reasoning for the metric"""

    evaluation_examples: Optional[str]
    """The evaluation examples for the metric"""

    name: Optional[str] = None
    """Human-readable name of the metric"""

    description: Optional[str] = None
    """Human-readable description of what the metric measures"""

    score_type: Optional[str] = None  # string or enum
    """The score type of the metric eg. numeric, categorical, etc."""

    metric_type: Optional[MetricType] = None  # string or enum
    """The type of the metric eg. rag, generation, classification"""

    ground_truth_required: Optional[bool] = False
    """Whether the metric requires a ground truth reference"""

    context_required: Optional[bool] = False
    """Whether the metric requires a context"""

    parameters: Dict[str, Any] = field(default_factory=dict)
    """Additional parameters specific to this metric implementation"""


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
