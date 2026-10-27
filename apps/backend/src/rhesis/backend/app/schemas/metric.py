import json
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from pydantic import UUID4, BaseModel, ConfigDict, ValidationError, model_validator

from rhesis.backend.app.schemas.base import Base, ServerIdentity
from rhesis.backend.app.schemas.metric_types import ScoreType, ThresholdOperator
from rhesis.backend.app.schemas.references import RequirementReference
from rhesis.backend.app.schemas.tag import Tag
from rhesis.backend.app.schemas.type_lookup import TypeLookup


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
    # Settings of the metric's class, e.g. a trajectory metric's match mode, and under
    # "target" what the metric judges.
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


def builtin_metric_class(class_name: Optional[str]) -> Optional[type]:
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


def metric_targets(
    class_name: Optional[str],
    *,
    ground_truth_required: bool = False,
    accepted: Optional[List[str]] = None,
) -> Tuple[List[Any], Any]:
    """The targets a metric can take, and the one it takes when none is chosen (None when
    one must be chosen). They come from its class, from ``accepted`` (the parameters of an
    SDK metric's function), or else are a judge's. Raises ImportError on a core install."""
    from rhesis.sdk.metrics.targets import (
        TargetKind,
        default_target,
        supported_targets,
        targets_for,
    )

    compares = ("response",) if ground_truth_required else ()
    cls = builtin_metric_class(class_name)
    if accepted is not None:
        supported = targets_for(accepted, compares=compares)
        reads_turns = bool({"input", "output"} & set(accepted))
        default = TargetKind.TURN if reads_turns else TargetKind.RUN
    elif cls is not None:
        supported = supported_targets(cls, compares=compares)
        default = default_target(cls)
    else:
        supported = targets_for(("input", "output", "trace"), compares=compares)
        default = TargetKind.TURN
    return supported, default if default in supported else None


def check_metric_config(
    class_name: Optional[str],
    config: Optional[Dict[str, Any]],
    *,
    ground_truth_required: bool = False,
    accepted: Optional[List[str]] = None,
    default_target: bool = False,
) -> Optional[Dict[str, Any]]:
    """Refuse settings the metric's class would refuse when the metric runs (ValueError).

    ``config["target"]`` says what the metric judges; the other keys are the class's own
    settings. With ``default_target``, a config without a target gets the metric's default.
    """
    if config is None and not default_target:
        return config
    try:
        from rhesis.sdk.metrics.targets import Target, check_target
    except ImportError:  # a core install, which runs no native metric
        return config

    cls = builtin_metric_class(class_name)
    settings = {k: v for k, v in (config or {}).items() if k != "target"}
    if hasattr(cls, "validate_config"):
        settings = cls.validate_config(settings)
    supported, default = metric_targets(
        class_name, ground_truth_required=ground_truth_required, accepted=accepted
    )
    if (config or {}).get("target") is None:
        if default_target and default is not None:
            return {**settings, "target": {"on": default.value}}
        return settings if config is not None else None
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
    metric. A config sent without a target gets the metric's default, since the whole config
    is replaced."""

    def current(field: str) -> Any:
        value = getattr(update, field)
        sent = field in update.model_fields_set and value is not None
        return value if sent else getattr(stored, field, None)

    return check_metric_config(
        current("class_name"),
        update.config,
        ground_truth_required=bool(current("ground_truth_required")),
        accepted=accepted_params(current("evaluation_examples")),
        default_target=update.config is not None,
    )


class _ChecksConfig:
    """Checked on writes only: a stored row is read back whatever it holds."""

    #: Whether a metric sent without a target is stored with its default one.
    fills_default_target: ClassVar[bool] = False

    @model_validator(mode="before")
    @classmethod
    def refuse_metric_scope(cls, data: Any) -> Any:
        # Ignoring it would quietly turn a Multi-Turn metric into one judging each turn.
        if isinstance(data, dict) and "metric_scope" in data:
            raise ValueError(
                'metric_scope was replaced by the target: send config {"target": {"on": '
                '"turn"}} for a metric judging each turn, or "conversation" for one judging '
                "the whole conversation. Upgrade rhesis-sdk if it sent this."
            )
        return data

    @model_validator(mode="after")
    def validate_config(self):
        self.config = check_metric_config(
            self.class_name,
            self.config,
            ground_truth_required=bool(self.ground_truth_required),
            accepted=accepted_params(self.evaluation_examples),
            default_target=self.fills_default_target,
        )
        return self


class MetricCreate(_ChecksConfig, MetricBase):
    # Stored, so every reader (the response, the UI, MCP) sees what the metric judges.
    fills_default_target: ClassVar[bool] = True

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


class Metric(MetricBase, ServerIdentity):
    id: UUID4
    tags: Optional[List[Tag]] = []
    # Override string fields with relationship objects for response
    backend_type: Optional[TypeLookup] = None
    metric_type: Optional[TypeLookup] = None
    # The targets the metric can take, for an editor to offer; None on a core install.
    supported_targets: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _read_supported_targets(self):
        try:
            supported, _ = metric_targets(
                self.class_name,
                ground_truth_required=bool(self.ground_truth_required),
                accepted=accepted_params(self.evaluation_examples),
            )
        except ImportError:
            return self
        self.supported_targets = [kind.value for kind in supported]
        return self


class TargetChoice(BaseModel):
    """One target from the SDK's registry, as an editor offers it."""

    on: str
    label: str
    description: str
    per_span: bool


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
