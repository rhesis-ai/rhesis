import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import UUID4, ConfigDict, Field, ValidationError, field_validator, model_validator

from rhesis.backend.app.schemas.base import Base, ServerIdentity
from rhesis.backend.app.schemas.metric_types import ScoreType, ThresholdOperator
from rhesis.backend.app.schemas.references import RequirementReference
from rhesis.backend.app.schemas.tag import Tag
from rhesis.backend.app.schemas.type_lookup import TypeLookup


class MetricScope(str, Enum):
    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"


class MetricBase(Base):
    name: str
    description: Optional[str] = None
    evaluation_prompt: str
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    score_type: ScoreType
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    reference_score: Optional[str] = (
        None  # @deprecated: kept for transition, use categories instead
    )
    categories: Optional[List[str]] = None  # List of valid categories for categorical metrics
    passing_categories: Optional[List[str]] = None  # Categories that indicate pass
    threshold: Optional[float] = None
    threshold_operator: Optional[ThresholdOperator] = ThresholdOperator.GREATER_THAN_OR_EQUAL
    explanation: Optional[str] = None
    # ID fields (used internally)
    metric_type_id: Optional[UUID4] = None
    backend_type_id: Optional[UUID4] = None
    model_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    # String fields (from SDK, will be converted to IDs)
    metric_type: Optional[str] = None
    backend_type: Optional[str] = None
    class_name: Optional[str] = None
    ground_truth_required: Optional[bool] = False
    context_required: Optional[bool] = False
    evaluation_examples: Optional[str] = None
    metric_scope: Optional[List[MetricScope]] = None
    # Settings of the metric's class, e.g. a trajectory metric's match mode.
    config: Optional[Dict[str, Any]] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


def accepted_params(evaluation_examples: Optional[str]) -> Optional[List[str]]:
    """The parameters an SDK metric's function declares, which metric sync records under
    ``sdk_connection`` in ``evaluation_examples``; None for any other metric."""
    try:
        data = json.loads(evaluation_examples or "")
    except (json.JSONDecodeError, TypeError):
        return None
    connection = data.get("sdk_connection") if isinstance(data, dict) else None
    accepted = connection.get("accepted_params") if isinstance(connection, dict) else None
    return accepted if isinstance(accepted, list) else None


def _metric_class(class_name: Optional[str]) -> Optional[type]:
    """The SDK class a built-in metric is built from, native or DeepEval."""
    from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory

    factory = RhesisMetricFactory()
    if class_name in factory.list_supported_metrics():
        return factory.metric_class(class_name)
    if not class_name or not class_name.startswith(("DeepEval", "DeepTeam")):
        return None
    try:
        from rhesis.sdk.metrics.providers.deepeval.factory import DeepEvalMetricFactory
    except ImportError:
        return None
    return DeepEvalMetricFactory._metrics.get(class_name)


def check_metric_config(
    class_name: Optional[str],
    config: Optional[Dict[str, Any]],
    *,
    ground_truth_required: bool = False,
    accepted: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Refuse settings the metric's class would refuse when the metric runs (ValueError).

    ``config["target"]`` says what the metric judges; the other keys are the class's own
    settings. The targets a metric can take come from its class, from ``accepted`` (the
    parameters of an SDK metric's function), or else are a judge's.
    """
    if config is None:
        return config
    try:
        from rhesis.sdk.metrics.targets import Target, check_target, supported_targets, targets_for
    except ImportError:  # a core install, which runs no native metric
        return config

    cls = _metric_class(class_name)
    settings = {k: v for k, v in config.items() if k != "target"}
    if hasattr(cls, "validate_config"):
        settings = cls.validate_config(settings)
    if config.get("target") is None:
        return settings
    compares = ("response",) if ground_truth_required else ()
    if accepted is not None:
        supported = targets_for(accepted, compares=compares)
    elif cls is not None:
        supported = supported_targets(cls, compares=compares)
    else:
        supported = targets_for(("input", "output", "trace"), compares=compares)
    try:
        target = check_target(cls, Target.coerce(config["target"]), supported)
    except ValidationError as e:
        problems = "; ".join(
            f"{' -> '.join(str(loc) for loc in err['loc']) or 'target'}: {err['msg']}"
            for err in e.errors()
        )
        raise ValueError(f"Invalid target: {problems}") from None
    return {**settings, "target": target.to_config()}


def check_updated_config(update: "MetricUpdate", stored: Any) -> Optional[Dict[str, Any]]:
    """``check_metric_config`` for an update, reading what it doesn't send from the stored
    metric."""

    def current(field: str) -> Any:
        value = getattr(update, field)
        sent = field in update.model_fields_set and value is not None
        return value if sent else getattr(stored, field, None)

    return check_metric_config(
        current("class_name"),
        update.config,
        ground_truth_required=bool(current("ground_truth_required")),
        accepted=accepted_params(current("evaluation_examples")),
    )


class _ChecksConfig:
    """Checked on writes only: a stored row is read back whatever it holds."""

    @model_validator(mode="after")
    def validate_config(self):
        self.config = check_metric_config(
            self.class_name,
            self.config,
            ground_truth_required=bool(self.ground_truth_required),
            accepted=accepted_params(self.evaluation_examples),
        )
        return self


class MetricCreate(_ChecksConfig, MetricBase):
    # Required on create, unlike the rest of MetricBase. A metric with no scope is
    # filtered out by every execution path, so accepting one silently creates dead
    # configuration that never evaluates and reports no error. Enforced here rather
    # than only in the UI so the SDK, MCP, and the Architect agent are covered too;
    # the metric table also carries a CHECK constraint as a backstop.
    metric_scope: List[MetricScope] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_score_type_fields(self) -> "MetricCreate":
        if self.score_type == ScoreType.NUMERIC:
            if self.min_score is None:
                raise ValueError("min_score is required for numeric metrics")
            if self.max_score is None:
                raise ValueError("max_score is required for numeric metrics")
            if self.threshold is None:
                raise ValueError("threshold is required for numeric metrics")
        elif self.score_type == ScoreType.CATEGORICAL:
            if not self.categories or len(self.categories) < 2:
                raise ValueError("at least 2 categories are required for categorical metrics")
            if not self.passing_categories or len(self.passing_categories) < 1:
                raise ValueError("at least 1 passing category is required for categorical metrics")
        return self


class MetricUpdate(_ChecksConfig, MetricBase):
    """The route checks ``config`` again against the stored metric, for the fields the update
    doesn't send (``check_updated_config``)."""

    name: Optional[str] = None
    evaluation_prompt: Optional[str] = None
    score_type: Optional[ScoreType] = None
    threshold_operator: Optional[ThresholdOperator] = None

    @field_validator("metric_scope")
    @classmethod
    def scope_cannot_be_emptied(cls, v: Optional[List[MetricScope]]) -> Optional[List[MetricScope]]:
        """None means "not being updated"; an empty list would disable the metric."""
        if v is not None and len(v) == 0:
            raise ValueError("metric_scope cannot be empty")
        return v


class Metric(MetricBase, ServerIdentity):
    id: UUID4
    tags: Optional[List[Tag]] = []
    # Override string fields with relationship objects for response
    backend_type: Optional[TypeLookup] = None
    metric_type: Optional[TypeLookup] = None

    model_config = ConfigDict(from_attributes=True)


class ModelReference(Base, ServerIdentity):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MetricDetail(Metric):
    name: Optional[str] = None
    model: Optional[ModelReference] = None
    requirements: Optional[List[RequirementReference]] = []


class GenerateMetricRequest(Base):
    """Request body for POST /metrics/generate.

    The LLM uses the prompt to produce all required metric fields.
    """

    prompt: str


class ImproveMetricRequest(Base):
    """Request body for POST /metrics/{metric_id}/improve.

    The LLM uses the prompt to update the existing metric fields.
    """

    prompt: str
