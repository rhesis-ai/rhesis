import dataclasses
import inspect
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.app.schemas.metric_types import ScoreType
from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.utils import diagnose_invalid_metric
from rhesis.sdk.metrics import BaseMetric, MetricConfig
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config

logger = logging.getLogger(__name__)


def build_metric_evaluate_params(
    metric: BaseMetric,
    input_text: str,
    output_text: str,
    expected_output: str,
    context: List[str],
    conversation_history: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build kwargs for metric.evaluate() from evaluation inputs using introspection.

    Inspects the metric's evaluate signature and only includes parameters
    that are actually defined (e.g., ContextualRelevancy doesn't need output).

    Args:
        metric: The metric instance
        input_text: The input query or question
        output_text: The actual output from the LLM
        expected_output: The expected or reference output
        context: List of context strings used for the response
        conversation_history: Optional conversation history for conversational metrics
        metadata: Optional metadata dict
        tool_calls: Optional list of tool calls

    Returns:
        Dict of kwargs to pass to metric.evaluate()
    """
    sig = inspect.signature(metric.evaluate)
    params = sig.parameters

    kwargs: Dict[str, Any] = {}
    if "input" in params:
        kwargs["input"] = input_text
    if "output" in params:
        kwargs["output"] = output_text
    if "expected_output" in params:
        kwargs["expected_output"] = expected_output
    if "context" in params:
        kwargs["context"] = context
    if "conversation_history" in params and conversation_history is not None:
        kwargs["conversation_history"] = conversation_history
    if "metadata" in params and metadata is not None:
        kwargs["metadata"] = metadata
    if "tool_calls" in params and tool_calls is not None:
        kwargs["tool_calls"] = tool_calls
    if "goal" in params:
        kwargs["goal"] = input_text

    return kwargs


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
        config["threshold"] = metric.threshold if metric.threshold is not None else 0.5
        config["threshold_operator"] = metric.threshold_operator
        if metric.min_score is not None:
            config["min_score"] = metric.min_score
        if metric.max_score is not None:
            config["max_score"] = metric.max_score

    config = backend_config_to_sdk_config(config)
    field_names = {f.name for f in dataclasses.fields(MetricConfig)}
    filtered = {k: v for k, v in config.items() if k in field_names}
    cfg = MetricConfig(**filtered)
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
