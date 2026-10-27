import dataclasses
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.app.schemas.metric_types import ScoreType
from rhesis.backend.metrics.inputs import EvaluationInputs
from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.utils import diagnose_invalid_metric
from rhesis.sdk.metrics import BaseMetric, Expectations, MetricConfig, MetricResult
from rhesis.sdk.metrics.targets import a_evaluate_target, evaluate_target
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config

#: Where ``metric.config`` keeps the metric's target, beside the metric's own settings.
TARGET_KEY = "target"

logger = logging.getLogger(__name__)


def _get_metric_signature(metric: BaseMetric) -> Any:
    """Return the parameter map for the method that will actually be called.

    Prefers a_evaluate because that is what the evaluation pipeline invokes.
    Falls back to evaluate when a_evaluate only carries *args/**kwargs (the
    BaseMetric default), which would yield no named parameters to inspect.
    """
    a_eval_params = inspect.signature(metric.a_evaluate).parameters
    named = {
        name
        for name, p in a_eval_params.items()
        if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        and name != "self"
    }
    if named:
        return a_eval_params
    return inspect.signature(metric.evaluate).parameters


def metric_wants_trace(metric: BaseMetric) -> bool:
    """Whether the metric declares a ``trace`` parameter."""
    return "trace" in _get_metric_signature(metric)


def wants_trace(metric: BaseMetric, target: Optional[Dict[str, Any]]) -> bool:
    """Whether evaluating the metric reads the trace: it declares one, or judges a target."""
    return target is not None or metric_wants_trace(metric)


def evaluate_metric(
    metric: BaseMetric,
    inputs: EvaluationInputs,
    target: Optional[Dict[str, Any]] = None,
    verdict: Optional[Callable[[MetricResult], Optional[bool]]] = None,
) -> MetricResult:
    """Run the metric on what its target names, or as it declares when it has none."""
    if target is None:
        return metric.evaluate(**build_metric_evaluate_params(metric, inputs))
    expectations = _expectations_for(metric, inputs.expectations)
    return evaluate_target(metric, inputs.load_trace(), target, expectations, verdict)


async def a_evaluate_metric(
    metric: BaseMetric,
    inputs: EvaluationInputs,
    target: Optional[Dict[str, Any]] = None,
    verdict: Optional[Callable[[MetricResult], Optional[bool]]] = None,
) -> MetricResult:
    """Async ``evaluate_metric``."""
    if target is None:
        return await metric.a_evaluate(**build_metric_evaluate_params(metric, inputs))
    expectations = _expectations_for(metric, inputs.expectations)
    return await a_evaluate_target(metric, inputs.load_trace(), target, expectations, verdict)


def build_metric_evaluate_params(metric: BaseMetric, inputs: EvaluationInputs) -> Dict[str, Any]:
    """The kwargs for ``metric.a_evaluate()``: whichever of ``input``, ``output``, ``trace``
    and ``expectations`` its signature declares. The trace is read only for a metric that
    declares it."""
    params = _get_metric_signature(metric)
    values = {
        "input": lambda: inputs.input_text,
        "output": lambda: inputs.output_text,
        "trace": inputs.load_trace,
        "expectations": lambda: _expectations_for(metric, inputs.expectations),
    }
    return {name: read() for name, read in values.items() if name in params}


def _expectations_for(metric: BaseMetric, expectations: Optional[Expectations]) -> Expectations:
    """The expectations a metric is scored against.

    A metric that requires a reference answer gets an empty one when the test has none
    (conversations, production traces), as it always has. TBE 3 reports these as not
    applicable instead.
    """
    if not getattr(metric, "requires_ground_truth", False):
        return expectations
    if expectations is None:
        return Expectations(response="")
    if expectations.response is None:
        return expectations.model_copy(update={"response": ""})
    return expectations


#: Generic fallback for a numeric metric row that never had a threshold set.
_DEFAULT_NUMERIC_THRESHOLD = 0.5


def _default_threshold_for(metric: MetricModel) -> float:
    """Threshold to use when the DB row doesn't set one.

    Goal achievement gets its own default from the SDK. Using the generic 0.5 here meant a
    re-score disagreed with the live run that produced the same conversation, since a live run
    builds its judge through Penelope and got 0.7. Same conversation, two verdicts at 0.6.
    """
    from rhesis.sdk.metrics.providers.native.goal_achievement_judge import (
        DEFAULT_GOAL_ACHIEVEMENT_THRESHOLD,
    )

    if (getattr(metric, "class_name", "") or "") == "GoalAchievementJudge":
        return DEFAULT_GOAL_ACHIEVEMENT_THRESHOLD
    return _DEFAULT_NUMERIC_THRESHOLD


def metric_model_to_config(metric: MetricModel) -> MetricConfig:
    """Convert a Metric database model to a MetricConfig."""
    common_fields = [
        "name",
        "class_name",
        "description",
        "evaluation_prompt",
        "evaluation_steps",
        "reasoning",
        "evaluation_examples",
        "score_type",
        "ground_truth_required",
        "context_required",
        "metric_scope",
    ]
    config = {field: getattr(metric, field, None) for field in common_fields}
    config["backend"] = metric.backend_type.type_value if metric.backend_type else "rhesis"
    config["name"] = config["name"] or f"Metric_{metric.id}"
    config["description"] = config["description"] or f"Metric evaluation for {metric.class_name}"
    config["score_type"] = config["score_type"] or ScoreType.NUMERIC.value

    score_type = metric.score_type or ScoreType.NUMERIC.value
    if score_type == ScoreType.CATEGORICAL.value:
        config["categories"] = metric.categories
        config["passing_categories"] = metric.passing_categories
    else:
        config["threshold"] = (
            metric.threshold if metric.threshold is not None else _default_threshold_for(metric)
        )
        config["threshold_operator"] = metric.threshold_operator
        if metric.min_score is not None:
            config["min_score"] = metric.min_score
        if metric.max_score is not None:
            config["max_score"] = metric.max_score

    config = backend_config_to_sdk_config(config)
    field_names = {f.name for f in dataclasses.fields(MetricConfig)}
    filtered = {k: v for k, v in config.items() if k in field_names}
    cfg = MetricConfig(**filtered)
    # Needed so _generate_unique_metric_keys can break a (name, class_name)
    # tie deterministically when two distinct metrics happen to share both.
    cfg.id = str(metric.id) if metric.id else None
    if isinstance(metric.config, dict) and metric.config:
        # The target says what the metric judges; the rest are its own settings.
        settings = {k: v for k, v in metric.config.items() if k != TARGET_KEY}
        cfg.target = metric.config.get(TARGET_KEY)
        if settings:
            cfg.parameters = {**(cfg.parameters or {}), **settings}
    if model_id := (str(metric.model_id) if metric.model_id else None):
        cfg.parameters = dict(cfg.parameters or {})
        cfg.parameters["model_id"] = model_id
    if metric.model and metric.model.provider_type:
        cfg.parameters = dict(cfg.parameters or {})
        cfg.parameters["provider"] = metric.model.provider_type.type_value
        cfg.parameters["model"] = metric.model.model_name
    return cfg


def dict_to_metric_config(config: Dict[str, Any]) -> MetricConfig:
    """Convert a dict to MetricConfig, flattening nested 'parameters' into top-level."""
    params = config.get("parameters") or {}
    if not isinstance(params, dict):
        params = {}
    merged = {**config, **params}
    params = dict(params)
    for key in ("model_id", "provider", "model"):
        if key in merged:
            params[key] = merged[key]
    merged["parameters"] = params
    field_names = {f.name for f in dataclasses.fields(MetricConfig)}
    filtered = {k: v for k, v in merged.items() if k in field_names}
    return MetricConfig(**filtered)


def normalize_config(
    config: Union[Dict[str, Any], MetricConfig, MetricModel],
) -> MetricConfig:
    """Normalize any supported config type to MetricConfig."""
    if isinstance(config, MetricConfig):
        return config
    if isinstance(config, MetricModel):
        return metric_model_to_config(config)
    if isinstance(config, dict):
        return dict_to_metric_config(config)
    raise TypeError(f"Unsupported config type: {type(config).__name__}")


def validate_metric_configs(
    metrics: List[Union[Dict[str, Any], MetricConfig, MetricModel]],
) -> Tuple[List[MetricConfig], Dict[str, Any]]:
    """Normalize and validate raw metric configs.

    Returns:
        Tuple of (valid MetricConfig list, dict of invalid metric error results).
    """
    metric_configs: List[MetricConfig] = []
    invalid_metric_results: Dict[str, Any] = {}

    for i, raw_config in enumerate(metrics):
        try:
            config = normalize_config(raw_config)
        except (TypeError, ValueError) as e:
            invalid_key = f"InvalidMetric_{i}"
            if isinstance(e, TypeError):
                reason = f"Invalid config type: {type(raw_config).__name__}"
            else:
                reason = str(e)
            invalid_metric_results[invalid_key] = MetricResultBuilder.error(
                reason=reason,
                backend="unknown",
                name=invalid_key,
                class_name="Unknown",
                description=reason,
                error=reason,
                threshold=0.0,
            )
            logger.warning(f"Invalid metric config for metric {i}: {reason}")
            continue

        error_reason = diagnose_invalid_metric(config)
        if error_reason and error_reason != "unknown validation error":
            invalid_key = f"InvalidMetric_{i}"
            backend_str = getattr(config.backend, "value", config.backend) or "unknown"
            invalid_metric_results[invalid_key] = MetricResultBuilder.error(
                reason=f"Invalid metric configuration: {error_reason}",
                backend=backend_str,
                name=config.name or invalid_key,
                class_name=config.class_name or "Unknown",
                description=f"Failed to load metric: {error_reason}",
                error=error_reason,
                threshold=0.0,
            )
            logger.warning(f"Invalid metric configuration {i}: {error_reason}")
        else:
            metric_configs.append(config)

    if invalid_metric_results:
        logger.warning(
            f"Found {len(invalid_metric_results)} invalid metrics that will be reported as errors"
        )

    logger.debug(
        f"Using {len(metric_configs)} valid metrics and "
        f"{len(invalid_metric_results)} invalid metrics"
    )

    return metric_configs, invalid_metric_results
