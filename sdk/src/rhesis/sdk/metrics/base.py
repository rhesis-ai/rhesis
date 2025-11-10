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
from dataclasses import dataclass
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
    CONVERSATIONAL = "conversational"


class MetricScope(str, Enum):
    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


@dataclass
class MetricConfig:
    # Backend required items
    class_name: Optional[str] = None
    backend: Optional[Union[str, Backend]] = Backend.RHESIS
    name: Optional[str] = None
    description: Optional[str] = None
    score_type: Optional[Union[str, ScoreType]] = None  # string or enum
    metric_type: Optional[Union[str, MetricType]] = None  # string or enum
    metric_scope: Optional[List[Union[str, MetricScope]]] = None  # list of scopes
    requires_ground_truth: Optional[bool] = False
    requires_context: Optional[bool] = False

    def __post_init__(self):
        if isinstance(self.backend, str):
            try:
                self.backend = Backend(self.backend.lower())
            except ValueError:
                raise ValueError(f"Unknown backend: {self.backend}")

        if isinstance(self.score_type, str):
            try:
                self.score_type = ScoreType(self.score_type.lower())
            except ValueError:
                raise ValueError(f"Unknown score type: {self.score_type}")

        if isinstance(self.metric_type, str):
            try:
                self.metric_type = MetricType(self.metric_type.lower())
            except ValueError:
                raise ValueError(f"Unknown metric type: {self.metric_type}")

        if self.metric_scope is not None:
            converted_scopes = []
            for scope in self.metric_scope:
                if isinstance(scope, str):
                    try:
                        converted_scopes.append(MetricScope(scope))
                    except ValueError:
                        raise ValueError(f"Unknown metric scope: {scope}")
                else:
                    converted_scopes.append(scope)
            self.metric_scope = converted_scopes


class MetricResult:
    """Result of a metric evaluation."""

    def __init__(self, score: float, details: Optional[Dict[str, Any]] = None):
        self.score = score
        self.details = details or {}

    def __str__(self):
        return f"MetricResult(score={self.score}, details={self.details})"


class BaseMetric(ABC):
    """Base class for all evaluation metrics."""

    def __init__(self, config: MetricConfig, model: Optional[Union[BaseLLM, str]] = None):
        self.name = config.name
        self.description = config.description
        self.score_type = config.score_type
        self.metric_type = config.metric_type
        self.metric_scope = config.metric_scope
        self.requires_ground_truth = config.requires_ground_truth
        self.requires_context = config.requires_context
        self.class_name = config.class_name
        self.backend = config.backend

        self.model = self.set_model(model)

    def set_model(self, model: Optional[Union[BaseLLM, str]]) -> BaseLLM:
        if isinstance(model, BaseLLM):
            return model
        return get_model(model)

    @abstractmethod
    def evaluate(
        self,
        *args: Any,
        **kwargs: Any,
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
