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

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field

from rhesis.sdk.models.base import BaseDecisionModel, BaseLLM
from rhesis.sdk.models.base import BaseModel as SdkModel
from rhesis.sdk.models.factory import get_model

F = TypeVar("F", bound=Callable[..., Any])


class Backend(str, Enum):
    RHESIS = "rhesis"
    DEEPEVAL = "deepeval"
    CUSTOM = "custom"
    GARAK = "garak"
    SDK = "sdk"


class ScoreType(str, Enum):
    BINARY = "binary"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class MetricType(str, Enum):
    # Original SDK metric types
    RAG = "rag"
    GENERATION = "generation"
    CLASSIFICATION = "classification"
    CONVERSATIONAL = "conversational"
    # Backend API metric types
    GRADING = "grading"
    API_CALL = "api-call"
    CUSTOM_CODE = "custom-code"
    CUSTOM_PROMPT = "custom-prompt"
    FRAMEWORK = "framework"


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
    backend: Optional[Union[str, Backend]] = Backend.CUSTOM  # Default to custom for SDK metrics
    name: Optional[str] = None
    description: Optional[str] = None
    score_type: Optional[Union[str, ScoreType]] = None  # string or enum
    metric_type: Optional[Union[str, MetricType]] = (
        MetricType.CUSTOM_PROMPT
    )  # Default for SDK metrics
    metric_scope: Optional[List[Union[str, MetricScope]]] = None  # list of scopes
    explanation: Optional[str] = None
    requires_ground_truth: Optional[bool] = False
    requires_context: Optional[bool] = False
    id: Optional[str] = None  # ID from backend when pulled

    # Scoring fields (optional on base; subclasses add validation)
    threshold: Optional[float] = None
    threshold_operator: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    categories: Optional[List[str]] = None
    passing_categories: Optional[List[str]] = None
    reference_score: Optional[str] = None

    # Evaluation fields
    evaluation_prompt: Optional[str] = None
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    evaluation_examples: Optional[str] = None

    # Extra parameters bucket (e.g. for factory kwargs)
    parameters: Optional[Dict[str, Any]] = None

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


class MetricResult(BaseModel):
    """Result of a metric evaluation."""

    score: Optional[Union[float, str]] = Field(
        default=None,
        description=(
            "The evaluation score (float for numeric/binary metrics, str for categorical metrics, "
            "None when the result is inconclusive)"
        ),
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional evaluation details"
    )

    def __str__(self):
        return f"MetricResult(score={self.score}, details={self.details})"


class UnsupportedModelType(ValueError):
    """A metric was given a kind of model it can't judge with (e.g. a decision model)."""


#: A judge model: a text LLM, or a decision model for metrics that accept one.
JudgeModel = Union[BaseLLM, BaseDecisionModel]


def resolve_metric_model(
    model: Optional[Union[JudgeModel, str]],
    metric_name: Optional[str],
    supported_model_types: tuple = (BaseLLM,),
) -> JudgeModel:
    """Build the metric's model and refuse a kind of model the metric can't judge with."""
    resolved = get_model(model) if model is None or isinstance(model, str) else model
    # Only real models of the wrong kind are refused; duck-typed stand-ins pass as before.
    if isinstance(resolved, SdkModel) and not isinstance(resolved, supported_model_types):
        raise UnsupportedModelType(
            f"Metric '{metric_name}' can't judge with {resolved.get_model_name()}, a "
            f"{resolved.MODEL_TYPE} model. Choose a different model for this metric."
        )
    return resolved


class BaseMetric(ABC):
    """Base class for all evaluation metrics."""

    # The model kinds this metric can judge with; metrics that can use a decision model add it.
    SUPPORTED_MODEL_TYPES: tuple = (BaseLLM,)

    def __init__(self, config: MetricConfig, model: Optional[Union[JudgeModel, str]] = None):
        self.name = config.name
        self.description = config.description
        self.score_type = config.score_type
        self.metric_type = config.metric_type
        self.metric_scope = config.metric_scope
        self.requires_ground_truth = config.requires_ground_truth
        self.requires_context = config.requires_context
        self.class_name = config.class_name
        self.backend = config.backend
        self.id = config.id  # ID from backend when pulled

        self.model = self.set_model(model)

    @property
    def is_goal_achievement_metric(self) -> bool:
        """
        Identify whether this metric is a goal achievement metric.

        Goal achievement metrics provide detailed criteria evaluations and
        may need special handling to avoid data duplication in systems
        that maintain separate detailed goal evaluation data.

        Returns:
            False by default. Subclasses like GoalAchievementJudge override this.
        """
        return False

    def set_model(self, model: Optional[Union[JudgeModel, str]]) -> JudgeModel:
        return resolve_metric_model(model, self.name, self.SUPPORTED_MODEL_TYPES)

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

    async def a_evaluate(self, *args: Any, **kwargs: Any) -> MetricResult:
        """
        Async version of evaluate with a default to_thread fallback.

        Metrics with native async implementations should override this.
        """
        return await asyncio.to_thread(self.evaluate, *args, **kwargs)


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
