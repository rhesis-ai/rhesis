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
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model

F = TypeVar("F", bound=Callable[..., Any])


class Backend(str, Enum):
    RHESIS = "rhesis"
    DEEPEVAL = "deepeval"


class ScoreType(str, Enum):
    BINARY = "binary"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class MetricType(str, Enum):
    RAG = "rag"
    GENERATION = "generation"
    CLASSIFICATION = "classification"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


@dataclass
class MetricConfig:
    """Standard configuration for a metric instance

    Backend required items:
    - class_name
    - backend
    - name
    - description
    - score_type
    - metric_type
    """

    # Backend required items

    class_name: Optional[str] = None
    """The class name of the metric to instantiate (e.g., 'DeepEvalContextualRecall')"""

    backend: Optional[Union[str, Backend]] = Backend.RHESIS
    """The backend/framework to use for this metric (e.g., 'deepeval')"""

    name: Optional[str] = None
    """Human-readable name of the metric"""

    description: Optional[str] = None
    """Human-readable description of what the metric measures"""

    score_type: Optional[Union[str, ScoreType]] = None  # string or enum
    """The score type of the metric eg. numeric, categorical, etc."""

    metric_type: Optional[Union[str, MetricType]] = None  # string or enum
    """The type of the metric eg. rag, generation, classification"""

    ground_truth_required: Optional[bool] = False
    """Whether the metric requires a ground truth reference"""

    context_required: Optional[bool] = False
    """Whether the metric requires a context"""

    # Custom parameters

    evaluation_prompt: str = None
    """The evaluation prompt for the metric"""

    evaluation_steps: Optional[str] = None
    """The evaluation steps for the metric"""

    reasoning: Optional[str] = None
    """The reasoning for the metric"""

    evaluation_examples: Optional[str] = None
    """The evaluation examples for the metric"""

    parameters: Dict[str, Any] = field(default_factory=dict)
    """Additional parameters specific to this metric implementation"""

    def __post_init__(self):
        # The config accept both string and enum for score_type and metric_type. However, the object
        # will keep it as a string for easier serialization

        if self.backend is not None:
            self.backend = self._validate_enum_value(self.backend, Backend, "backend")

        if self.score_type is not None:
            self.score_type = self._validate_enum_value(self.score_type, ScoreType, "score_type")

        if self.metric_type is not None:
            self.metric_type = self._validate_enum_value(
                self.metric_type, MetricType, "metric_type"
            )

    def _validate_enum_value(
        self, value: Union[str, Enum], enum_class: type, field_name: str
    ) -> str:
        if isinstance(value, str):
            try:
                enum_instance = enum_class(value)
                return enum_instance.value
            except ValueError:
                allowed = [member.value for member in enum_class]
                raise ValueError(f"Invalid {field_name} value: {value}. Allowed values: {allowed}")
        elif isinstance(value, enum_class):
            return value.value
        else:
            raise ValueError(f"Invalid {field_name} type: {type(value)}")


class MetricResult:
    """Result of a metric evaluation."""

    def __init__(self, score: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        self.score = score
        self.details = details or {}

    def __str__(self):
        return f"MetricResult(score={self.score}, details={self.details})"


class BaseMetric(ABC):
    """Base class for all evaluation metrics."""

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        score_type: Optional[Union[str, ScoreType]] = None,
        metric_type: Optional[Union[str, MetricType]] = None,
        model: Optional[Union[BaseLLM, str]] = None,
        **kwargs,
    ):
        self.name = name
        self.description = description

        self.score_type = score_type
        if isinstance(self.score_type, str):
            try:
                self.score_type = ScoreType(self.score_type)
            except ValueError:
                allowed = [member.value for member in ScoreType]
                raise ValueError(
                    f"Invalid score_type value: {self.score_type}. Allowed values: {allowed}"
                )

        self.metric_type = metric_type
        if isinstance(self.metric_type, str):
            try:
                self.metric_type = MetricType(self.metric_type)
            except ValueError:
                allowed = [member.value for member in MetricType]
                raise ValueError(
                    f"Invalid metric_type value: {self.metric_type}. Allowed values: {allowed}"
                )

        self.model = self.set_model(model)

    def set_model(self, model: Optional[Union[BaseLLM, str]]) -> BaseLLM:
        if model is None:
            return get_model()  # Use default model
        if isinstance(model, BaseLLM):
            return model
        elif isinstance(model, str) or model is None:
            return get_model(model)
        else:
            raise ValueError(f"Invalid model type: {type(model)}")

    @abstractmethod
    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        """
        Evaluate the metric on the given input, output, and context.

        Args:
            input: The input query/question
            output: The system output/response
            expected_output: Optional ground truth/reference output
            context: Optional list of context strings

        Returns:
            MetricResult: The evaluation result
        """


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
